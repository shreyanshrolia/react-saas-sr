# Grihkari - Product Requirements Document

## Overview
**Grihkari** is a daily clothes ironing management mobile app (Expo / React Native) targeting Indian households and local Iron Man (Dhobi) vendors.

## Users
Two roles in one app, chosen at signup:
- **Iron Man (Dhobi)**: vendor managing clients, entries, bills.
- **Client (Household)**: views their own clothes & bills.

Phone number is the unique login key (10-digit Indian).

## Core Features Built
1. **Auth**: Phone + password (bcrypt), JWT (30 days), Expo SecureStore on client.
2. **Iron Man flow**:
   - Add/edit/delete clients (auto-link if client phone already signed up)
   - Add daily entries (multi-item: cloth_type, quantity, rate)
   - Mark entries returned
   - View per-client detail
   - Monthly bill auto-generation/aggregation
   - Mark bills paid/unpaid
   - Reports: monthly, yearly, client-wise
3. **Client flow**:
   - Home: this-month total, pending clothes, linked Iron Man(s)
   - Bills: filter all/paid/unpaid
   - Reports: monthly, yearly
4. **Subscription (MVP placeholder)**:
   - 7-day free trial on signup
   - Plans: Iron Man ₹49/mo, Client ₹19/mo
   - **Razorpay payment NOT wired** — needs API keys. Currently "activate" button extends subscription locally for 30 days (demo).
5. **i18n**: English + Hindi toggle (storage-persisted).
6. **Currency**: INR throughout.

## Backend
- FastAPI + Motor MongoDB
- JWT auth, bcrypt password hashing
- Endpoints under `/api/*`:
  - `auth/signup`, `auth/login`, `auth/me`
  - `clients` CRUD
  - `entries` CRUD + `/return`
  - `bills` list + `/generate` + `/:id/paid`
  - `reports/monthly`, `reports/yearly`, `reports/by-client`
  - `subscription/plans`, `subscription/activate`
  - `my/iron-men` (client side)

## Pending (needs user input)
- Real Razorpay payment integration (Key ID + Secret + Plan IDs)
- PDF bill export
- Push notifications for due bills (only on user request, after deployment)
