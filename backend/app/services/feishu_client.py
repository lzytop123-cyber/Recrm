"""飞书开放平台 HTTP 客户端：应用身份 token 与通讯录只读接口。"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings, get_settings
from app.services.feishu_auth import FeishuAuthError, require_feishu_enabled


class FeishuClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = require_feishu_enabled(settings)
        self._tenant_token: str | None = None
        self._http: httpx.AsyncClient | None = None

    async def __aenter__(self) -> FeishuClient:
        self._http = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def get_tenant_access_token(self) -> str:
        if self._tenant_token:
            return self._tenant_token
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        body = {
            "app_id": self.settings.feishu_app_id,
            "app_secret": self.settings.feishu_app_secret,
        }
        data = self._json(await self._request("POST", url, json=body))
        if data.get("code", 0) != 0 or not data.get("tenant_access_token"):
            raise FeishuAuthError(data.get("msg") or "获取 tenant_access_token 失败", detail=data)
        self._tenant_token = str(data["tenant_access_token"])
        return self._tenant_token

    async def _request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        if self._http is not None:
            return await self._http.request(method, url, headers=headers, params=params, json=json)
        async with httpx.AsyncClient(timeout=30.0) as client:
            return await client.request(method, url, headers=headers, params=params, json=json)

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        token = await self.get_tenant_access_token()
        url = f"https://open.feishu.cn{path}"
        headers = {"Authorization": f"Bearer {token}"}
        resp = await self._request("GET", url, headers=headers, params=params or {})
        data = self._json(resp)
        if data.get("code", 0) != 0:
            raise FeishuAuthError(data.get("msg") or f"飞书接口失败: {path}", detail=data)
        return data

    async def _post(self, path: str, json: dict[str, Any] | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
        token = await self.get_tenant_access_token()
        url = f"https://open.feishu.cn{path}"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}
        resp = await self._request("POST", url, headers=headers, params=params or {}, json=json or {})
        data = self._json(resp)
        if data.get("code", 0) != 0:
            raise FeishuAuthError(data.get("msg") or f"飞书接口失败: {path}", detail=data)
        return data

    @staticmethod
    def _json(resp: httpx.Response) -> dict[str, Any]:
        try:
            return resp.json()
        except Exception as exc:
            raise FeishuAuthError(f"飞书响应无效: HTTP {resp.status_code}") from exc

    async def list_contact_scopes(self) -> dict[str, list[str]]:
        """获取应用通讯录授权范围内的部门 / 用户 / 用户组 ID。"""
        department_ids: list[str] = []
        user_ids: list[str] = []
        group_ids: list[str] = []
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {
                "user_id_type": "open_id",
                "department_id_type": "open_department_id",
                "page_size": 100,
            }
            if page_token:
                params["page_token"] = page_token
            data = await self._get("/open-apis/contact/v3/scopes", params=params)
            payload = data.get("data") or {}
            department_ids.extend(str(x) for x in (payload.get("department_ids") or []))
            user_ids.extend(str(x) for x in (payload.get("user_ids") or []))
            group_ids.extend(str(x) for x in (payload.get("group_ids") or []))
            if not payload.get("has_more"):
                break
            page_token = payload.get("page_token")
            if not page_token:
                break
        return {
            "department_ids": department_ids,
            "user_ids": user_ids,
            "group_ids": group_ids,
        }

    async def get_department(self, department_id: str) -> dict[str, Any]:
        data = await self._get(
            f"/open-apis/contact/v3/departments/{department_id}",
            params={"department_id_type": "open_department_id"},
        )
        return (data.get("data") or {}).get("department") or {}

    async def get_user(self, user_id: str, *, user_id_type: str = "open_id") -> dict[str, Any]:
        data = await self._get(
            f"/open-apis/contact/v3/users/{user_id}",
            params={
                "user_id_type": user_id_type,
                "department_id_type": "open_department_id",
            },
        )
        return (data.get("data") or {}).get("user") or {}

    async def iter_department_children(
        self,
        department_id: str = "0",
        *,
        fetch_child: bool = False,
    ) -> list[dict[str, Any]]:
        """拉取子部门；fetch_child=True 时一次拉回整棵子树。"""
        items: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {
                "department_id_type": "open_department_id",
                "page_size": 50,
                "fetch_child": "true" if fetch_child else "false",
            }
            if page_token:
                params["page_token"] = page_token
            data = await self._get(
                f"/open-apis/contact/v3/departments/{department_id}/children",
                params=params,
            )
            payload = data.get("data") or {}
            items.extend(payload.get("items") or [])
            if not payload.get("has_more"):
                break
            page_token = payload.get("page_token")
            if not page_token:
                break
        return items

    async def iter_users_by_department(self, department_id: str) -> list[dict[str, Any]]:
        """拉取部门直属用户（分页聚合）。"""
        items: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {
                "department_id": department_id,
                "department_id_type": "open_department_id",
                "user_id_type": "open_id",
                "page_size": 50,
            }
            if page_token:
                params["page_token"] = page_token
            data = await self._get("/open-apis/contact/v3/users/find_by_department", params=params)
            payload = data.get("data") or {}
            items.extend(payload.get("items") or [])
            if not payload.get("has_more"):
                break
            page_token = payload.get("page_token")
            if not page_token:
                break
        return items

    async def query_user_tasks(
        self,
        *,
        user_ids: list[str],
        check_date_from: int,
        check_date_to: int,
        employee_type: str = "employee_id",
    ) -> list[dict[str, Any]]:
        """获取打卡结果。employee_type: employee_id | employee_no（不支持 open_id）。"""
        if not user_ids:
            return []
        data = await self._post(
            "/open-apis/attendance/v1/user_tasks/query",
            params={"employee_type": employee_type},
            json={
                "user_ids": user_ids,
                "check_date_from": check_date_from,
                "check_date_to": check_date_to,
            },
        )
        return list((data.get("data") or {}).get("user_task_results") or [])


def get_feishu_client(settings: Settings | None = None) -> FeishuClient:
    return FeishuClient(settings or get_settings())
