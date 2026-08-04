# Organization Permission Boundaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent users with organization read access from mutating organization data, resetting passwords, or synchronizing Feishu contacts.

**Architecture:** Keep `org:view` as the read boundary, add `org:manage` for local organization mutations and credential resets, and add `org:sync` for the external Feishu synchronization boundary. Route dependencies remain the authoritative backend guard; the organization page uses the same permission codes to hide unavailable actions.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, Vue 3, Pinia, TypeScript.

## Global Constraints

- Do not change employee transfer, termination, or handover behavior in this task.
- Do not grant organization mutation permissions to executive or middle-manager seed roles.
- The system administrator seed role receives all three organization permissions.
- Backend authorization is authoritative; frontend visibility is defense-in-depth only.

---

### Task 1: Lock organization writes behind explicit permissions

**Files:**
- Create: `backend/tests/api/test_org_permissions.py`
- Modify: `backend/app/api/v1/org.py`
- Modify: `backend/app/seed.py`
- Modify: `frontend/src/views/org/OrgView.vue`

**Interfaces:**
- Consumes: `PermissionChecker(required: Iterable[str])`, `useUserStore().hasPermission(code)`
- Produces: permission codes `org:view`, `org:manage`, and `org:sync`

- [ ] **Step 1: Write failing API authorization tests**

Create real FastAPI integration tests that build users with `org:view`, `org:manage`, or `org:sync`, authenticate through `/api/v1/auth/login`, and assert:

```python
assert client.get("/api/v1/org/departments", headers=view_headers).status_code == 200
assert client.post(
    "/api/v1/org/departments",
    headers=view_headers,
    json={"name": "越权部门", "code": "NOPE"},
).status_code == 403
assert client.post(
    f"/api/v1/org/employees/{target.id}/reset-password",
    headers=view_headers,
    json={"password": "changed123"},
).status_code == 403
assert client.post("/api/v1/org/feishu/sync", headers=view_headers).status_code == 403
```

Also assert an `org:manage` user can create a department while still receiving 403 from `/feishu/sync`.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/api/test_org_permissions.py -q
```

Expected: the read-only user receives success or reaches business logic on at least one write endpoint instead of 403.

- [ ] **Step 3: Add permission codes and route guards**

Add to `PERMISSIONS`:

```python
("管理组织", "org:manage", "org"),
("同步组织", "org:sync", "org"),
```

Keep GET routes on `org:view`. Require `org:manage` for department and employee POST/PATCH/DELETE routes and password reset. Require `org:sync` for `/org/feishu/sync`.

- [ ] **Step 4: Verify focused tests are GREEN**

Run the focused pytest command again and require zero failures.

- [ ] **Step 5: Align frontend action visibility**

Import `useUserStore`, create:

```ts
const userStore = useUserStore()
const canManageOrg = computed(() => userStore.hasPermission('org:manage'))
const canSyncOrg = computed(() => userStore.hasPermission('org:sync'))
```

Use `v-if` so create/edit/delete employee and department controls require `canManageOrg`, while the Feishu synchronization button requires `canSyncOrg`. Read-only filters, tables, and details remain visible.

- [ ] **Step 6: Run regression verification**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend
npm run build
```

Require zero pytest failures and a successful frontend production build.
