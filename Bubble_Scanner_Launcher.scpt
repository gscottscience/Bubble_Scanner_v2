#!/usr/bin/osascript
# AppleScript-based Bubble Scanner Launcher

tell application "System Events"
    # Show starting notification
    display notification "Starting Bubble Scanner..." with title "Bubble Scanner"
end tell

# Kill any existing Flask processes
do shell script "pkill -f 'python.*app.py' 2>/dev/null || true"

# Wait a moment
delay 2

# Change to project directory and start Flask
try
    do shell script "cd '/Users/gscott/Desktop/bubble_scanner_v2_web' && python3 app.py > /tmp/bubble_scanner.log 2>&1 &"
    
    # Wait for server to start
    delay 8
    
    # Test if server is responding
    try
        do shell script "curl -s http://localhost:5001 >/dev/null"
        
        # Success! Open browser
        do shell script "open http://localhost:5001"
        
        # Show success notification
        tell application "System Events"
            display notification "Access the app at http://localhost:5001" with title "Bubble Scanner Started" sound name "Glass"
        end tell
        
    on error
        # Server not responding
        display dialog "Server started but not responding. Please restart your Mac and try again." buttons {"OK"} default button "OK" with title "Bubble Scanner Error"
    end try
    
on error errorMessage
    # Failed to start
    display dialog "Failed to start Bubble Scanner: " & errorMessage buttons {"OK"} default button "OK" with title "Bubble Scanner Error"
end try