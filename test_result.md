#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================

user_problem_statement: "Build mobile app Grihkari for managing daily clothes ironing business with Iron Man (vendor) and Client roles. User requested admin panel UI to reset passwords for users who call the helpline."

frontend:
  - task: "Admin Panel UI - Login screen"
    implemented: true
    working: "NA"
    file: "/app/frontend/app/(admin)/login.tsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
        - working: "NA"
          agent: "main"
          comment: "Created admin login screen at /(admin)/login that posts to POST /api/admin/login and stores token via storage.secureSet under key grihkari_admin_token. Auto-redirects to dashboard if already logged in. Entry point: long-press (1.2s) on the shirt logo on /(auth)/login navigates to admin login."

  - task: "Admin Panel UI - Dashboard (list + search + reset password)"
    implemented: true
    working: true
    file: "/app/frontend/app/(admin)/dashboard.tsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: "Dashboard lists users via GET /api/admin/users?admin_token=... with debounced search by name/phone. Each user row has a Reset button that opens a modal to enter (or auto-generate) a new password, posting to POST /api/admin/users/{user_id}/reset-password. Success modal shows credentials to share. 401 responses clear admin token and route back to admin login. Sign-out clears the admin token."
        - working: false
          agent: "testing"
          comment: "Iter 6: All flows pass except logout. Alert.alert on react-native-web does not fire multi-button onPress handlers, so the admin can never sign out from the web preview."
        - working: true
          agent: "main"
          comment: "Replaced Alert.alert with a state-driven RN Modal (testIDs admin-logout-cancel, admin-logout-confirm). Verified via Playwright on web: clicking admin-logout shows modal; admin-logout-confirm clears token and routes to /(admin)/login. Reset/search/list flows untouched."

  - task: "Admin API client (frontend)"
    implemented: true
    working: "NA"
    file: "/app/frontend/src/api/admin.ts"
    stuck_count: 0
    priority: "medium"
    needs_retesting: true
    status_history:
        - working: "NA"
          agent: "main"
          comment: "Added adminApi with login/listUsers/resetPassword. Stores token separately from user JWT in SecureStore. Attaches admin_token as query param per backend contract."

metadata:
  created_by: "main_agent"
  version: "1.1"
  test_sequence: 6
  run_ui: true

test_plan:
  current_focus:
    - "Admin Panel UI - Login screen"
    - "Admin Panel UI - Dashboard (list + search + reset password)"
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
    - agent: "main"
      message: "Built the missing Admin Panel frontend. Routes: /(admin)/login and /(admin)/dashboard. Backend admin endpoints already exist and were verified in prior iterations. Please test: (1) navigate to /(admin)/login, sign in with admin password 'grihkari-admin-2026' (it should accept and route to dashboard), (2) on dashboard verify the list loads, search by phone like '9999999991' filters results, (3) tap Reset for any user, enter a new password (min 6 chars) or use auto-generate, submit, expect success modal with credentials, (4) verify the user can then log in via /(auth)/login with the new password, (5) wrong admin password shows error, (6) sign out clears token and routes back to /(admin)/login. Frontend-only testing requested. Admin credential is in /app/memory/test_credentials.md."


backend:
  - task: "Backend modular refactor (server.py split into core/models/services/routes)"
    implemented: true
    working: "NA"
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
        - working: "NA"
          agent: "main"
          comment: "Refactored 1683-line server.py into ~60-line entrypoint + core/ (config, db, security, time_utils, deps), models/ (auth, clients, entries, notifications, bills, reports, subscription), services/ (users, clients, entries, bills, notifications, subscription), routes/ (auth, admin, clients, entries, notifications, bills, reports, subscription, misc). NO route paths or contracts changed. All endpoints still under /api. Verified manually via curl: /api/, /api/auth/login, /api/admin/login, /api/admin/users all 200. Need full regression to confirm every endpoint behaves identically."

agent_communication:
    - agent: "main"
      message: "Backend refactor complete. server.py now only wires together CORS, the master /api APIRouter, and startup/shutdown. All 9 route groups live under /app/backend/routes/. No URL paths or response shapes changed. Quick smoke tests via curl pass. Please run a BACKEND-ONLY regression covering: (1) /api/auth (signup, login, me, security-questions, forgot-password, reset-password), (2) /api/admin (login + list + reset, including q= search and 401s), (3) /api/clients CRUD + delete-request/confirm/deny linked flow, (4) /api/entries CRUD + return-confirm/deny + delete-request/confirm/deny, (5) /api/notifications, (6) /api/bills (generate, list, payments, mark-paid, delete-payment + carry-forward across months), (7) /api/reports/{monthly,yearly,by-client}, (8) /api/subscription/{plans,create-order,verify-payment,activate}, (9) /api/my/iron-men. Use credentials from /app/memory/test_credentials.md. Skip frontend."
