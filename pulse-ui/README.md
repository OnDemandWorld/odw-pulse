# Pulse UI

React 18 + TypeScript + Vite frontend for the Pulse multilingual content generation platform.

## Overview

The Pulse UI is a single-page application that provides:
- **Dashboard** — Overview of recent activity, content stats
- **Generate** — Content generation form with market/language selection
- **Content** — Browse, search, and manage generated content with review workflow
- **Content Detail** — View content versions, annotations, export
- **Bulk Jobs** — Monitor bulk generation jobs, download CSV results
- **Experiments** — Create and manage A/B experiments, view results
- **Settings** — Workspace configuration, brand voice, integrations

## Tech Stack

| Technology | Purpose |
|---|---|
| React 18 | UI framework |
| TypeScript | Type safety |
| Vite | Build tool and dev server |
| TanStack Query v5 | Server state management |
| React Router v6 | Client-side routing |
| Axios | HTTP client |
| Tailwind CSS | Utility-first CSS |

## Quick Start

```bash
cd pulse-ui
npm install
npm run dev
```

Open http://localhost:5173. The API URL defaults to `http://localhost:8000` (override with `VITE_API_URL`).

## Build

```bash
# Type check
npm run typecheck

# Production build
npm run build

# Preview production build
npm run preview

# Lint
npm run lint
```

**Build output:** ~277 KB JS (88 KB gzipped), ~13 KB CSS (3 KB gzipped)

## Pages & Routes

| Path | Component | Description |
|---|---|---|
| `/` | `Dashboard` | Overview with recent content, stats |
| `/generate` | `Generate` | Content generation form |
| `/content` | `ContentList` | Browse and search content |
| `/content/:id` | `ContentDetail` | View content, versions, annotations |
| `/bulk-jobs` | `BulkJobs` | Monitor bulk generation jobs |
| `/experiments` | `Experiments` | A/B experiment management |
| `/settings` | `Settings` | Workspace configuration |

## Project Structure

```
pulse-ui/
├── src/
│   ├── main.tsx           # App entry point
│   ├── App.tsx            # Router configuration
│   ├── index.css          # Global styles + Tailwind
│   ├── api/
│   │   └── client.ts      # Axios HTTP client
│   ├── components/
│   │   ├── Layout.tsx     # App shell with navigation
│   │   └── NavLink.tsx    # Navigation link component
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── Generate.tsx
│   │   ├── ContentList.tsx
│   │   ├── ContentDetail.tsx
│   │   ├── BulkJobs.tsx
│   │   ├── Experiments.tsx
│   │   └── Settings.tsx
│   └── types/
│       └── index.ts       # TypeScript type definitions
├── index.html             # HTML entry point
├── vite.config.ts         # Vite configuration
├── tsconfig.json          # TypeScript config
├── tailwind.config.js     # Tailwind configuration
├── postcss.config.js      # PostCSS configuration
├── package.json           # Dependencies
└── Dockerfile             # Container build
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | Base URL for API requests |

## API Client

The API client (`src/api/client.ts`) is an Axios instance configured with:
- Base URL from `VITE_API_URL`
- JSON content type
- Request/response interceptors for error handling

All API calls use TanStack Query hooks for caching, deduplication, and background refetching.

## State Management

- **Server state:** TanStack Query (React Query) — all API data is cached and managed by the library
- **Client state:** No global store. Component-level state with `useState`/`useReducer`
- **URL state:** React Router for navigation state

## Styling

Tailwind CSS utility classes throughout. Configuration in `tailwind.config.js`.

Key patterns:
- Responsive design with `sm:`, `md:`, `lg:` breakpoints
- Dark mode support via `dark:` variant (configurable)
- Consistent spacing with Tailwind's spacing scale
- Custom colors defined in Tailwind config

## Dependencies

**Runtime:** react, react-dom, react-router-dom, @tanstack/react-query, axios

**Dev:** typescript, vite, @vitejs/plugin-react, tailwindcss, postcss, autoprefixer, eslint, @typescript-eslint/*

## Known Limitations

1. **No authentication UI** — Login/register forms are not yet implemented. API calls assume a valid JWT token.
2. **No error boundaries** — Unhandled errors crash the whole app.
3. **No loading states** — Some pages don't show loading spinners during data fetches.
4. **No pagination** — Content list loads all items (no infinite scroll or page controls).
5. **No real-time updates** — No WebSocket/SSE for live content updates.
6. **Basic styling** — Tailwind utility classes without a design system or component library.

## Future Improvements

- Add authentication UI (login, register, password reset)
- Add error boundaries for graceful error handling
- Add loading states and skeleton screens
- Add pagination and infinite scroll
- Add real-time updates via WebSocket/SSE
- Add a component library (shadcn/ui or similar)
- Add dark mode toggle
- Add internationalization (i18n) for the UI itself
- Add unit tests for components (React Testing Library)
- Add E2E tests (Playwright)
