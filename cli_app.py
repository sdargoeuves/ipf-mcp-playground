import asyncio
import os
import threading
import time
from pathlib import Path

import dotenv
from agents import Agent, Runner, SQLiteSession, set_trace_processors
from agents.extensions.models.litellm_model import LitellmModel
from agents.mcp import MCPServerStdio
from langsmith.wrappers import OpenAIAgentsTracingProcessor

dotenv.load_dotenv(dotenv.find_dotenv())

DB_HISTORY_CONVERSATION = "ipfabric_conversations.db"
DEFAULT_SESSION_ID = "ipfabric_user"


class LoadingAnimation:
    """Simple loading animation for CLI."""
    
    def __init__(self, message="🔍 Analyzing"):
        self.message = message
        self.running = False
        self.thread = None
        self.frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        # Alternative frames you can try:
        # self.frames = ["🌍", "🌎", "🌏"]
        # self.frames = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]
        # self.frames = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█", "▇", "▆", "▅", "▄", "▃", "▂"]
        
    def _animate(self):
        """Animation loop."""
        frame_index = 0
        while self.running:
            frame = self.frames[frame_index % len(self.frames)]
            # Clear line and print animation
            print(f"\r{frame} {self.message}...", end="", flush=True)
            time.sleep(0.1)
            frame_index += 1
    
    def start(self):
        """Start the loading animation."""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._animate, daemon=True)
            self.thread.start()
    
    def stop(self):
        """Stop the loading animation and clear the line."""
        if self.running:
            self.running = False
            if self.thread:
                self.thread.join(timeout=0.2)
            # Clear the animation line
            print("\r" + " " * 50 + "\r", end="", flush=True)


class ConversationManager:
    """Manages SQLite conversation database operations."""

    def __init__(self, db_name: str = DB_HISTORY_CONVERSATION):
        self.db_path = Path(db_name)
        self.db_files = [self.db_path, Path(f"{db_name}-shm"), Path(f"{db_name}-wal")]

    def exists(self) -> bool:
        """Check if the database file exists."""
        return self.db_path.exists()

    def get_size(self) -> str:
        """Get human-readable database size."""
        if not self.exists():
            return "0 bytes"

        size_bytes = self.db_path.stat().st_size
        if size_bytes < 1024:
            return f"{size_bytes} bytes"
        elif size_bytes < 1024**2:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024**2):.1f} MB"

    def clear_database(self) -> bool:
        """Remove all database files. Returns True if successful."""
        if not self.exists():
            print(f"Database {self.db_path} does not exist.")
            return False

        success = True
        for db_file in self.db_files:
            if db_file.exists():
                try:
                    db_file.unlink()
                    print(f"✓ Removed {db_file.name}")
                except Exception as e:
                    print(f"✗ Error removing {db_file.name}: {e}")
                    success = False

        if success:
            # pause to ensure files are removed
            import time

            time.sleep(0.5)
            print("✓ Database cleared successfully")
        return success

    def prompt_for_session(self, user_id: str = DEFAULT_SESSION_ID) -> tuple[str, str | None]:
        """Interactive prompt to create appropriate session."""
        if not self.exists():
            print("No existing conversation history found, creating a new database to store conversations....")
            return (user_id, str(self.db_path))

        print(f"Found existing conversation history ({self.get_size()})")
        print("\nOptions:")
        print("1. Continue with existing conversations")
        print("2. Clear all history and start fresh")
        print("3. Exit")

        while True:
            choice = input("\nSelect option (1-3), default is 1: ").strip() or "1"

            if choice == "1":
                print("Loading existing conversations...")
                return (user_id, str(self.db_path))

            elif choice == "2":
                confirm = input("Are you sure you want to delete all conversation history? (Y/n): ")
                if confirm.lower() == "n" or confirm.lower() not in ["", "y", "yes"]:
                    print("Cancelled. Please choose another option.")
                elif self.clear_database():
                    print("Starting fresh with a new database...")
                    return (user_id, str(self.db_path))
                else:
                    print("Failed to clear history. Please try again.")
                    continue

            elif choice == "3":
                print("Exiting...")
                exit(0)

            else:
                print("Invalid choice. Please select 1-3.")


async def setup_agent():
    """Set up the IP Fabric agent with MCP server."""
    ipf_mcp_server = MCPServerStdio(
        name="IP Fabric Assistant MCP Server",
        params={
            "command": "uv",
            "args": ["run", "python", "src/mcp_ipf/server.py"],
        },
        client_session_timeout_seconds=60,
    )
    await ipf_mcp_server.__aenter__()

    ipfabric_agent = Agent(
        name="IP Fabric Assistant",
        handoff_description="Specialist agent for network visibility and analysis using IP Fabric snapshots",
        instructions=(
            "You are an expert in interpreting IP Fabric snapshot data with persistent conversation memory. "
            "IMPORTANT: You MAY have access to persistent conversation history from previous sessions. "
            "If this is a continuing conversation, you can remember previous interactions, user preferences, names, and context from past sessions. "
            "When users reference something from earlier conversations, check if you have that context and use it appropriately. "
            "If you do have access to previous conversation history, do not claim that you cannot remember - acknowledge and use that information. "
            "If this appears to be a new conversation with no prior history, that's perfectly normal. "
            "Use the tools provided by the MCP server to answer network-related questions. "
            "You can list snapshots, devices, interfaces, VLANS, routes, BGP neighbors or perform basic visibility triage using point-in-time snapshot data. "
            "All your answers should reflect what's currently available in the specified snapshot, if not specified, use the latest snapshot. "
            "You can give insights using multiple snapshot data points. "
            "Do not fabricate data. If a tool does not return results, explain that clearly. "
            "Unless the user directly asks for a specific snapshot, always use the latest snapshot. You can use the tool set_snapshot to change the snapshot context for your answers. "
            "Be aware that conversation history may be available from previous sessions - use this context when it exists to provide personalized and contextually relevant responses. "
            "If a user mentions their name, preferences, or specific network configurations and you have that information from past sessions, acknowledge and reference it appropriately."
        ),
        mcp_servers=[ipf_mcp_server],
        model=LitellmModel(model=os.getenv("AI_MODEL", "gpt-4.0"), api_key=os.getenv("AI_API_KEY")),
    )
    return ipfabric_agent, ipf_mcp_server


async def chat_loop(agent: Agent):
    """Main chat loop with improved UX."""
    # Set up conversation management
    conv_manager = ConversationManager()
    session_user_id, session_db_path = conv_manager.prompt_for_session()

    session = SQLiteSession(session_user_id, session_db_path)

    def show_help():
        """Display enhanced help message with better formatting."""
        print("\n" + "═" * 50)
        print(" " * 10 + "🌐 IP Fabric Assistant | 📖 Help")
        print("═" * 50)

        # Available Commands Section
        print("\n  🎮 Available Commands:\n")
        print("   • help      - Show this help message")
        print("   • clear     - Clear conversation history and exit")
        print("   • exit/quit - Exit the application")
        
        # Experimental Commands Section
        print("\n 🧪 Experimental Commands:")
        print("   ⚠️  Note: These commands may have varying results\n")
        print("   • /tools   - List available tools")
        print("   • /info    - Get IP Fabric instance information")
        
        # Example Questions Section
        print("\n 💡 What You Can Ask:")
        print("\n   🔍 Network Discovery:\n")
        print("     • \"Show me all devices in my network\"")
        print("     • \"What devices are in site ABC?\"")
        print("     • \"List all Cisco routers\"")
        print("\n   🌐 Interface & Connectivity:\n")
        print("     • \"Show interface status for router XYZ\"")
        print("     • \"What interfaces are down?\"")
        # print("     • \"Display BGP neighbors\"")
        print("\n   🛣️  Routing & VLANs:\n")
        print("     • \"Show routing table for device ABC\"")
        print("     • \"List all VLANs\"")
        print("     • \"What's the network topology?\"")
        print("\n   📊 Analysis & Comparison:\n")
        print("     • \"Compare table Device between snapshots A and snapshot B\"")
        print("     • \"Show network changes over time\"")
        # print("     • \"Analyze device performance\"")
        
        # Tips Section
        print("\n 💡 Tips:\n")
        print("   • Be specific with device names and sites")
        print("   • Use natural language - I understand context!")
        print("   • Ask follow-up questions to dive deeper")
        print("\n" + "═" * 50)
        print()

    show_help()

    while True:
        try:
            msg = input("\n💬 You: ").strip()

            if msg.lower() in ["exit", "quit"]:
                print("👋 Goodbye!")
                break

            elif msg.lower() == "help":
                show_help()
                continue

            elif msg.lower() == "clear":
                confirm = input("🗑️  Clear conversation history? (Y/n): ")
                if confirm.lower() == "n":
                    print("❌ Failed to clear history. Continuing...")
                else:
                    conv_manager = ConversationManager()
                    if conv_manager.clear_database():
                        print("✅ Conversation history cleared. Exiting chat.")
                        break
                continue

            elif not msg:
                continue

            # Start loading animation
            loader = LoadingAnimation("🤖 Assistant thinking")
            loader.start()

            try:
                # Use the session with Runner.run()
                result = await Runner.run(starting_agent=agent, input=msg, session=session)
                
                # Stop animation and show response
                loader.stop()
                print(f"🤖 Assistant: {result.final_output}\n")

            except Exception as e:
                loader.stop()
                print(f"🤖 Assistant: ❌ Error: {e}")
                print("Please try again or type 'exit' to quit.")

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("Please try again or type 'exit' to quit.")

async def main():
    """Main application entry point."""
    print("🚀 Starting IP Fabric Assistant...")

    try:
        # Set up agent
        print("🔧 Setting up agent and MCP server...")
        agent, mcp_server = await setup_agent()

        print("✅ Setup complete!")

        # Start chat loop
        await chat_loop(agent)

    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
    finally:
        # Clean up MCP server
        try:
            await mcp_server.__aexit__(None, None, None)
        except:
            pass


if __name__ == "__main__":
    set_trace_processors([OpenAIAgentsTracingProcessor()])
    asyncio.run(main())