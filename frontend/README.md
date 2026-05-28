# AP Workflow Agent - Frontend

React TypeScript frontend for the Accounts Payable Workflow Agent system.

## Project Structure

```
frontend/
├── src/
│   ├── components/          # Reusable React components
│   │   ├── Layout.tsx       # Main layout with navigation
│   │   └── ProtectedRoute.tsx # Route protection with auth
│   ├── context/             # React context providers
│   │   └── AuthContext.tsx  # Authentication state management
│   ├── hooks/               # Custom React hooks
│   │   ├── useInvoices.ts   # Invoice data fetching
│   │   ├── useExceptions.ts # Exception data fetching
│   │   ├── useApprovals.ts  # Approval data fetching
│   │   └── useWebSocket.ts  # WebSocket connection management
│   ├── lib/                 # Utility libraries
│   │   ├── api.ts           # Axios client with JWT interceptors
│   │   └── queryClient.ts   # React Query configuration
│   ├── types/               # TypeScript type definitions
│   │   └── index.ts         # All shared types
│   ├── App.tsx              # Main app component with routing
│   ├── main.tsx             # React entry point
│   └── index.css            # Global styles with Tailwind
├── index.html               # HTML entry point
├── vite.config.ts           # Vite configuration
├── tsconfig.json            # TypeScript configuration
├── tailwind.config.js       # Tailwind CSS configuration
├── postcss.config.js        # PostCSS configuration
├── .env                     # Environment variables
├── .env.example             # Example environment variables
└── package.json             # Dependencies and scripts
```

## Setup

### Prerequisites

- Node.js 18+ and npm/yarn
- Backend API running on `http://localhost:8000`

### Installation

```bash
cd frontend
npm install
```

### Development

```bash
npm run dev
```

The app will be available at `http://localhost:5173`

### Build

```bash
npm run build
```

### Type Checking

```bash
npm run type-check
```

## Key Features

### Authentication

- JWT token-based authentication
- Automatic token refresh on 401 responses
- Role-based access control (AP_CLERK, MANAGER, CFO)
- Protected routes with `ProtectedRoute` component

### API Client

- Axios-based HTTP client with base configuration
- Request interceptor: Automatically adds JWT token to Authorization header
- Response interceptor: Handles 401/403/500 errors
- Token management: `setAuthToken()`, `clearAuthToken()`, `getAuthToken()`

### Data Fetching

- React Query (TanStack Query v5) for server state management
- Custom hooks for invoices, exceptions, and approvals
- Automatic caching and refetching
- Mutation support for POST/PUT operations

### Real-Time Updates

- WebSocket connection for real-time exception notifications
- `useWebSocket` hook for managing WebSocket lifecycle
- Automatic reconnection with exponential backoff
- Event-based message handling

### Styling

- Tailwind CSS for utility-first styling
- Custom component classes in `index.css`
- Severity color coding (critical, high, medium, low)
- Responsive design with mobile support

## Environment Variables

```env
# API Configuration
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/ws

# Authentication
VITE_JWT_STORAGE_KEY=ap_workflow_token

# Feature Flags
VITE_ENABLE_DEMO_MODE=false
VITE_ENABLE_WEBSOCKET=true
```

## API Integration

The frontend communicates with the backend API at `/api/v1`:

### Invoices
- `GET /invoices` - List invoices
- `GET /invoices/{id}` - Get invoice details
- `POST /invoices/upload` - Upload PDF
- `POST /invoices/manual` - Create manual entry
- `PUT /invoices/{id}/status` - Update status

### Exceptions
- `GET /exceptions` - List exceptions
- `GET /exceptions/{id}` - Get exception details
- `PUT /exceptions/{id}/resolve` - Resolve exception

### Approvals
- `GET /approvals` - List approvals
- `GET /approvals/{id}` - Get approval details
- `POST /approvals/{id}/action` - Take approval action

### WebSocket
- `WS /ws/stream?token=<api_key>` - Real-time event stream

## Component Development

### Creating a New Page

1. Create component in `src/pages/`
2. Add route in `App.tsx`
3. Use custom hooks for data fetching
4. Wrap with `ProtectedRoute` if needed

### Using React Query

```typescript
import { useInvoices } from '@/hooks/useInvoices'

function MyComponent() {
  const { data: invoices, isLoading, error } = useInvoices()
  
  if (isLoading) return <div>Loading...</div>
  if (error) return <div>Error: {error.message}</div>
  
  return <div>{/* render invoices */}</div>
}
```

### Using WebSocket

```typescript
import { useWebSocket } from '@/hooks/useWebSocket'

function MyComponent() {
  const { send } = useWebSocket((event) => {
    console.log('Received event:', event)
  })
  
  return <div>{/* component */}</div>
}
```

## Testing

TODO: Add testing setup with Vitest and React Testing Library

## Deployment

TODO: Add deployment instructions for production builds

## License

Proprietary - Accounts Payable Workflow Agent
