#!/usr/bin/env python3
"""
Local USSD Simulator

Test the USSD flow without Africa's Talking.
Simulates the USSD experience in your terminal.

Usage:
    python test_ussd.py

Requirements:
    - Redis running locally
    - App dependencies installed
"""

import httpx
import uuid
import sys


class USSDSimulator:
    """Interactive USSD simulator for local testing."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session_id = f"sim-{uuid.uuid4().hex[:8]}"
        self.phone_number = "+26771234567"
        self.service_code = "*384*123#"
        self.text_history = []
    
    def send_request(self, user_input: str = "") -> str:
        """Send USSD request and return response."""
        
        # Build cumulative text
        if user_input:
            self.text_history.append(user_input)
        
        text = "*".join(self.text_history)
        
        try:
            response = httpx.post(
                f"{self.base_url}/ussd/callback",
                data={
                    "sessionId": self.session_id,
                    "phoneNumber": self.phone_number,
                    "serviceCode": self.service_code,
                    "text": text
                },
                timeout=10
            )
            return response.text
        except httpx.ConnectError:
            return "ERROR: Cannot connect to server. Is uvicorn running?"
        except Exception as e:
            return f"ERROR: {str(e)}"
    
    def display_screen(self, response: str):
        """Display USSD screen in terminal."""
        
        # Check if session ended
        is_end = response.startswith("END ")
        content = response[4:] if (response.startswith("CON ") or response.startswith("END ")) else response
        
        # Build display
        width = 40
        print("\n" + "┌" + "─" * width + "┐")
        print("│" + f" USSD - {self.service_code}".ljust(width) + "│")
        print("├" + "─" * width + "┤")
        
        # Split content into lines
        lines = content.split('\n')
        for line in lines:
            # Wrap long lines
            while len(line) > width - 2:
                print("│ " + line[:width-2] + " │")
                line = line[width-2:]
            print("│ " + line.ljust(width-2) + " │")
        
        print("└" + "─" * width + "┘")
        
        if is_end:
            print("\n[Session Ended]")
            return False
        return True
    
    def run(self):
        """Run interactive simulator."""
        
        print("\n" + "=" * 50)
        print("  USSD SIMULATOR - EduBot Demo")
        print("  Type 'quit' to exit, 'reset' to restart")
        print("=" * 50)
        
        # Initial menu
        response = self.send_request("")
        active = self.display_screen(response)
        
        while active:
            try:
                user_input = input("\nEnter selection: ").strip()
                
                if user_input.lower() == 'quit':
                    print("\nGoodbye!")
                    break
                
                if user_input.lower() == 'reset':
                    self.session_id = f"sim-{uuid.uuid4().hex[:8]}"
                    self.text_history = []
                    response = self.send_request("")
                    active = self.display_screen(response)
                    continue
                
                if not user_input:
                    continue
                
                response = self.send_request(user_input)
                active = self.display_screen(response)
                
            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
        
        print("\n[Simulator ended. Check console for SMS logs]")


def check_server():
    """Check if the server is running."""
    try:
        response = httpx.get("http://localhost:8000/health", timeout=5)
        return response.status_code == 200
    except:
        return False


if __name__ == "__main__":
    print("Checking server...")
    
    if not check_server():
        print("\n❌ Server not running!")
        print("\nStart the server first:")
        print("  uvicorn app.main:app --reload --port 8000")
        sys.exit(1)
    
    print("✓ Server is running")
    
    simulator = USSDSimulator()
    simulator.run()
