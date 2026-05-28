# Authentication and Layout Components

This document describes the authentication and layout components implemented for the AP Workflow Agent frontend.

## Overview

The authentication system provides:
- JWT token-based authentication
- Automatic token refresh before expiration
- Role-based access control (RBAC)
- Secure token storage in localStorage
- Protected routes with role enforcement
- Comprehensive navigation with user menu

## Components

### 1. LoginPage (`src/pages/LoginPage.tsx`)

The login page component provides a user-friendly interface for authentication.

**Features:**
- Email and password input fields
- Form validation
- Error message display
- Loading state during authentication
- Demo credentials display
- Responsive design with Tailwind CSS

**Usage:**
```tsx
import LoginPage from './pages/LoginPage'

// In your router
<Route path="/login" element={<LoginPage />} />
```

**Props:** None

**State:**
- `email`: User's email address
- `password`: User's password
- `error`: Error message from failed login
- `isLoading`: Loading state during authentication

### 2. AuthContext (`src/context/AuthContext.tsx`)

The authentication context manages the global authentication state and provides methods for login/logout.

**Features:**
- JWT token storage and retrieval
- Automatic token refresh scheduling
- User profile fetching
- Token expiration detection
- Graceful error handling

**Context Value:**
```typescript
interface AuthContextType {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  setUser: (user: User | null) => void
  refreshToken: () => Promise<boolean>
}
```

**Usage:**
```tsx
import { useAuth } from './context/AuthContext'

function MyComponent() {
  const { user, isAuthenticated, login, logout } = useAuth()
  
  return (
    <div>
      {isAuthenticated ? (
        <p>Welcome, {user?.email}</p>
      ) : (
        <p>Please log in</p>
      )}
    </div>
  )
}
```

### 3. useAuth Hook (`src/hooks/useAuth.ts`)

A custom hook for JWT token management with automatic refresh.

**Features:**
- Token encoding/decoding
- Token expiration detection
- Automatic refresh scheduling
- Configurable refresh intervals

**Usage:**
```tsx
import { useAuthTokenManagement } from './hooks/useAuth'

function MyComponent() {
  const { refreshToken, isTokenExpired } = useAuthTokenManagement()
  
  // Token will be automatically refreshed before expiration
}
```

**Configuration:**
- `TOKEN_REFRESH_INTERVAL`: 5 minutes (refresh every 5 minutes)
- `TOKEN_EXPIRY_BUFFER`: 1 minute (refresh 1 minute before expiration)

### 4. Navigation Component (`src/components/Navigation.tsx`)

The top navigation bar with logo, search, notifications, and user menu.

**Features:**
- Logo and brand display
- Navigation links (Dashboard, Payments, Settings)
- Search functionality
- Notifications icon with badge
- User avatar with dropdown menu
- Role-based badge display
- Responsive design

**Usage:**
```tsx
import Navigation from './components/Navigation'

function Layout() {
  return (
    <div>
      <Navigation />
      {/* Page content */}
    </div>
  )
}
```

**User Menu Features:**
- Display user email and role
- Role badge with color coding
- Department display (if available)
- Settings link
- Profile link
- Sign out button

**Role Colors:**
- CFO: Purple (`bg-purple-100 text-purple-800`)
- MANAGER: Blue (`bg-blue-100 text-blue-800`)
- AP_CLERK: Green (`bg-green-100 text-green-800`)

### 5. Layout Component (`src/components/Layout.tsx`)

The main layout wrapper that includes the navigation bar.

**Features:**
- Navigation integration
- Main content area with max-width constraint
- Responsive padding

**Usage:**
```tsx
import Layout from './components/Layout'

function App() {
  return (
    <Layout>
      {/* Page content */}
    </Layout>
  )
}
```

### 6. ProtectedRoute Component (`src/components/ProtectedRoute.tsx`)

A route wrapper that enforces authentication and role-based access control.

**Features:**
- Redirect to login if not authenticated
- Optional role-based access enforcement
- Loading state handling

**Usage:**
```tsx
import ProtectedRoute from './components/ProtectedRoute'

// Basic protection (authentication only)
<Route
  path="/dashboard"
  element={
    <ProtectedRoute>
      <Dashboard />
    </ProtectedRoute>
  }
/>

// Role-based protection
<Route
  path="/admin"
  element={
    <ProtectedRoute requiredRole="CFO">
      <AdminPanel />
    </ProtectedRoute>
  }
/>
```

**Props:**
- `children`: ReactNode - The component to render if authorized
- `requiredRole`: Optional role requirement ('AP_CLERK' | 'MANAGER' | 'CFO')

## Authentication Flow

### Login Flow

1. User enters email and password on LoginPage
2. Form is submitted to `/api/v1/auth/login` endpoint
3. Server returns JWT token and user profile
4. Token is stored in localStorage
5. User profile is stored in AuthContext
6. Token refresh is scheduled
7. User is redirected to dashboard

### Token Refresh Flow

1. Token refresh is scheduled when user logs in
2. Refresh occurs every 5 minutes or when token is about to expire
3. POST request to `/api/v1/auth/refresh` with current token
4. Server returns new token
5. New token is stored in localStorage
6. Next refresh is scheduled

### Logout Flow

1. User clicks "Sign Out" button
2. Token is cleared from localStorage
3. User profile is cleared from AuthContext
4. Refresh timeout is cancelled
5. User is redirected to login page

## API Integration

### Required Endpoints

The following API endpoints are required for authentication:

#### POST /api/v1/auth/login
Login with email and password.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "user123",
    "email": "user@example.com",
    "role": "AP_CLERK",
    "department": "Finance"
  }
}
```

#### POST /api/v1/auth/refresh
Refresh JWT token.

**Request:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "user123",
    "email": "user@example.com",
    "role": "AP_CLERK",
    "department": "Finance"
  }
}
```

#### GET /api/v1/auth/me
Get current user profile.

**Response:**
```json
{
  "user": {
    "id": "user123",
    "email": "user@example.com",
    "role": "AP_CLERK",
    "department": "Finance"
  }
}
```

## Token Storage

Tokens are stored in localStorage with the key `ap_workflow_token` (configurable via `VITE_JWT_STORAGE_KEY` environment variable).

**Security Considerations:**
- Tokens are stored in localStorage for persistence across page reloads
- Consider using httpOnly cookies for enhanced security in production
- Implement CSRF protection when using cookies
- Always use HTTPS in production

## Role-Based Access Control

Three roles are supported:

1. **AP_CLERK**: Basic invoice processing
   - View invoices
   - Process low-severity exceptions
   - Access AP_CLERK_QUEUE

2. **MANAGER**: Supervisory approval
   - View all invoices
   - Approve high-severity exceptions
   - Access MANAGER_QUEUE
   - View department analytics

3. **CFO**: Executive oversight
   - View all invoices and exceptions
   - Approve critical exceptions
   - Access CFO_ESCALATION_QUEUE
   - View company-wide analytics

## Environment Variables

Configure the following environment variables in `.env`:

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_JWT_STORAGE_KEY=ap_workflow_token
```

## Testing

Unit tests are provided in `src/__tests__/auth.test.ts` covering:

- JWT token encoding/decoding
- Token expiration detection
- Token refresh scheduling
- Authentication context
- Role-based access control
- Navigation component
- Login form validation
- Protected routes
- API client interceptors

Run tests with:
```bash
npm run test
```

## Error Handling

### Login Errors

- **Invalid credentials**: Display error message "Login failed. Please check your credentials and try again."
- **Network error**: Display error message with network error details
- **Server error**: Display error message "Server error. Please try again later."

### Token Refresh Errors

- **Refresh fails**: Token is cleared, user is redirected to login
- **Network error**: Retry with exponential backoff
- **Server error**: Fallback to manual login

### API Errors

- **401 Unauthorized**: Token is cleared, user is redirected to login
- **403 Forbidden**: Display error message "Access denied"
- **500 Server Error**: Display error message "Server error"

## Best Practices

1. **Always use HTTPS** in production to protect tokens in transit
2. **Implement token rotation** to minimize exposure of compromised tokens
3. **Use short token expiration times** (e.g., 1 hour) with refresh tokens
4. **Validate tokens on the server** for every API request
5. **Implement rate limiting** on login endpoint to prevent brute force attacks
6. **Log authentication events** for security auditing
7. **Clear tokens on logout** to prevent unauthorized access
8. **Use secure, httpOnly cookies** instead of localStorage for enhanced security

## Troubleshooting

### User stays on login page after successful login

- Check that the API returns both `token` and `user` in the response
- Verify that the token is valid and not expired
- Check browser console for errors

### Token refresh not working

- Verify that the `/api/v1/auth/refresh` endpoint is implemented
- Check that the token is being sent in the request
- Verify that the server returns a new token in the response

### Role-based access not working

- Verify that the user's role is correctly set in the API response
- Check that the ProtectedRoute component has the correct `requiredRole` prop
- Verify that the role values match exactly ('AP_CLERK', 'MANAGER', 'CFO')

### User menu not displaying

- Check that the Navigation component is rendered
- Verify that the user object is populated in AuthContext
- Check browser console for errors

## Future Enhancements

1. **Multi-factor authentication (MFA)** for enhanced security
2. **Social login** (Google, Microsoft) for convenience
3. **Session management** with activity timeout
4. **Remember me** functionality with secure cookies
5. **Password reset** functionality
6. **Account lockout** after failed login attempts
7. **Audit logging** of authentication events
8. **Two-factor authentication (2FA)** for sensitive operations
