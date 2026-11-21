# NEXTRADE AI Overview

Responsive React, TypeScript, Vite, and Tailwind dashboard frontend. Financial and market values are never seeded in the client; missing API data is shown as unavailable.

## Run locally

```powershell
npm install
npm run dev
npm run lint
npm test
npm run build
npm run backend:dev
npm run backend:test
```

Set `VITE_API_BASE_URL` when the backend is hosted separately. The optional `VITE_MARKET_WS_URL` overrides the same-origin market stream URL.

## Backend integration contract

- `GET /api/overview/dashboard?mode=spot|futures&range=24H|7D|30D|YTD` returns an `OverviewSnapshot` from `src/features/overview/types/index.ts`. Portfolio fields may be `null`; collections should be empty when no records exist.
- `GET /api/market/candles?symbol={symbol}&timeframe={timeframe}` returns `Candle[]`. `time` is a Unix timestamp in seconds; EMA and volume fields may be `null`.
- `PUT /api/overview/watchlist/favorite` accepts `{ "symbol": "...", "favorite": true }`.
- The WebSocket stream sends `{ "type": "market_update", "data": MarketQuote }` messages.

The backend should source account and trade records from its PostgreSQL-backed services and publish real agent executions. AI analysis and opportunity recommendations are only shown as recommendations when they include evidence and a valid analysis timestamp. No API credentials should be placed in frontend environment variables.
