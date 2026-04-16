# Session-Specific Answer Keys Implementation

## Overview
Answer keys are now stored per-session, just like school lists. This allows different UIL meets/sessions to have different answer keys without having to reconfigure them when switching sessions.

## Changes Made

### 1. Backend (app.py)
- **Modified `/api/keys` GET endpoint**: Now accepts a `session` query parameter and returns only the answer keys for that specific session
- **Modified `/api/keys` POST endpoint**: Now requires a `session` parameter in the request body and saves the answer key within that session's namespace

### 2. Answer Key Storage Structure
Answer keys are now stored with a session-based structure:
```json
{
  "Session Name 1": {
    "Test Name - Grade": "answer key string",
    "Science - Grades 6-8": "1:A,2:B,3:C..."
  },
  "Session Name 2": {
    "Test Name - Grade": "different answer key string",
    ...
  }
}
```

This applies to both files:
- `answer_keys_with_grades.json` (for grade-specific tests)
- `answer_keys.json` (for base tests)

### 3. Keys Management Page (keys.html)
- Added session information display at the top of the page
- Gets session name from URL parameter: `/keys?session=SessionName`
- Displays warning if no session is specified
- All GET and POST requests include the current session parameter
- Answer keys are isolated per session

### 4. Simple Scan Page (simple_scan.html)
- **Answer Keys Button**: Now uses `openAnswerKeysPage()` function instead of direct link
- **openAnswerKeysPage()** function:
  - Checks if a session is selected
  - Opens keys page with session parameter: `/keys?session=SessionName`
  - Shows alert if no session is selected
- **All Answer Key Operations**: Updated to include current session:
  - Loading answer keys in modal
  - Saving answer keys
  - Re-grading with answer keys
  - Initial scan auto-detection

## Benefits
1. **Session Isolation**: Each session has its own set of answer keys
2. **No Reconfiguration**: Switching between sessions automatically loads the correct answer keys
3. **Consistent with School Lists**: Uses the same pattern as session-specific school lists
4. **No Data Loss**: Old answer keys remain in place but are now nested under session names

## Migration Notes
- Existing global answer keys will need to be manually assigned to sessions
- Empty session files will be created as sessions are used
- The first time you use a session, you'll need to configure its answer keys

## Testing Workflow
1. Create or select a session in Simple Scan
2. Click "Manage Answer Keys" button
3. Keys page opens with session parameter
4. Add/modify answer keys for that session
5. Return to Simple Scan and scan sheets
6. Answer keys are automatically applied based on the selected session
7. Switch to a different session to verify isolation

## Files Modified
- `/app.py` - Backend endpoints for session-specific answer keys
- `/templates/keys.html` - Keys management page with session awareness
- `/templates/simple_scan.html` - Updated to pass session to keys page and use session-specific keys
