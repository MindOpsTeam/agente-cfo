#!/usr/bin/env python3
"""
evolution_client.py — Wrapper Python para Evolution API v2.

Referência: https://doc.evolution-api.com/
Auth: header `apikey: <key>`
"""
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional


class EvolutionClient:
    """
    Cliente HTTP de baixo nível para a Evolution API.

    Uso:
        client = EvolutionClient(base_url="https://evo.exemplo.com", api_key="abc123")
        client.fetch_instances()
        client.create_instance("vendas", webhook_url="https://...", webhook_secret="...")
    """

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._headers = {
            "Content-Type": "application/json",
            "apikey": api_key,
        }

    def _request(self, method: str, path: str, body: Optional[dict] = None, timeout: int = 20) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        data = json.dumps(body, default=str).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, headers=self._headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"HTTP {e.code} {method} {path}: {body_text}") from e

    # ── Instances ──────────────────────────────────────────────────────────────

    def fetch_instances(self) -> list[dict]:
        """GET /instance/fetchInstances → lista todas as instâncias."""
        result = self._request("GET", "/instance/fetchInstances")
        return result if isinstance(result, list) else []

    def get_connection_state(self, instance_name: str) -> dict:
        """GET /instance/connectionState/<name> → { instance: { state } }"""
        return self._request("GET", f"/instance/connectionState/{instance_name}")

    def create_instance(
        self,
        instance_name: str,
        webhook_url: str,
        webhook_secret: str = "",
        *,
        integration: str = "WHATSAPP-BAILEYS",
        reject_call: bool = True,
        msg_call: str = "Não atendemos chamadas por WhatsApp.",
        groups_ignore: bool = True,
        always_online: bool = False,
        read_messages: bool = False,
        read_status: bool = False,
    ) -> dict:
        """POST /instance/create → cria nova instância."""
        payload: dict = {
            "instanceName": instance_name,
            "integration": integration,
            "rejectCall": reject_call,
            "msgCall": msg_call,
            "groupsIgnore": groups_ignore,
            "alwaysOnline": always_online,
            "readMessages": read_messages,
            "readStatus": read_status,
            "webhook": {
                "enabled": True,
                "url": webhook_url,
                "byEvents": False,
                "base64": False,
                "headers": {"x-webhook-secret": webhook_secret} if webhook_secret else {},
                "events": [
                    "APPLICATION_STARTUP",
                    "QRCODE_UPDATED",
                    "MESSAGES_UPSERT",
                    "MESSAGES_UPDATE",
                    "MESSAGES_DELETE",
                    "SEND_MESSAGE",
                    "CONTACTS_UPSERT",
                    "CONTACTS_UPDATE",
                    "PRESENCE_UPDATE",
                    "CHATS_UPSERT",
                    "CHATS_UPDATE",
                    "CHATS_DELETE",
                    "GROUPS_UPSERT",
                    "GROUP_UPDATE",
                    "GROUP_PARTICIPANTS_UPDATE",
                    "CONNECTION_UPDATE",
                    "CALL",
                    "NEW_JWT_TOKEN",
                ],
            },
        }
        return self._request("POST", "/instance/create", body=payload)

    def connect_instance(self, instance_name: str) -> dict:
        """GET /instance/connect/<name> → retorna QR code base64."""
        return self._request("GET", f"/instance/connect/{instance_name}")

    def logout_instance(self, instance_name: str) -> dict:
        """DELETE /instance/logout/<name> → desconecta (mantém instância)."""
        return self._request("DELETE", f"/instance/logout/{instance_name}")

    def delete_instance(self, instance_name: str) -> dict:
        """DELETE /instance/delete/<name> → remove instância completamente."""
        return self._request("DELETE", f"/instance/delete/{instance_name}")

    def set_webhook(
        self,
        instance_name: str,
        webhook_url: str,
        webhook_secret: str = "",
    ) -> dict:
        """POST /webhook/set/<name> → atualiza webhook de instância existente."""
        payload = {
            "url": webhook_url,
            "byEvents": False,
            "base64": False,
            "headers": {"x-webhook-secret": webhook_secret} if webhook_secret else {},
            "events": [
                "APPLICATION_STARTUP", "QRCODE_UPDATED", "MESSAGES_UPSERT",
                "MESSAGES_UPDATE", "CONNECTION_UPDATE", "CALL",
            ],
        }
        return self._request("POST", f"/webhook/set/{instance_name}", body=payload)

    # ── Messages ───────────────────────────────────────────────────────────────

    def send_text(self, instance_name: str, number: str, text: str) -> dict:
        """POST /message/sendText/<instance> → envia mensagem de texto."""
        # Normaliza número (remove + se vier)
        number = number.lstrip("+")
        return self._request("POST", f"/message/sendText/{instance_name}", body={
            "number": number,
            "text": text,
        })

    def send_media(
        self,
        instance_name: str,
        number: str,
        media_url: str,
        media_type: str = "image",
        caption: str = "",
    ) -> dict:
        """POST /message/sendMedia/<instance> → envia mídia (image/video/audio/document)."""
        number = number.lstrip("+")
        return self._request("POST", f"/message/sendMedia/{instance_name}", body={
            "number": number,
            "mediatype": media_type,
            "media": media_url,
            "caption": caption,
        })

    def send_buttons(
        self,
        instance_name: str,
        number: str,
        title: str,
        description: str,
        buttons: list[dict],
    ) -> dict:
        """POST /message/sendButtons/<instance> → envia mensagem com botões."""
        number = number.lstrip("+")
        return self._request("POST", f"/message/sendButtons/{instance_name}", body={
            "number": number,
            "title": title,
            "description": description,
            "buttons": buttons,
        })

    # ── Contacts / Chats ───────────────────────────────────────────────────────

    def find_contacts(self, instance_name: str, query: str = "") -> list[dict]:
        """GET /contact/findContacts/<instance>?contactName=<query>"""
        path = f"/contact/findContacts/{instance_name}"
        if query:
            path += f"?contactName={urllib.parse.quote(query)}"
        result = self._request("GET", path)
        return result if isinstance(result, list) else []

    def fetch_chats(self, instance_name: str) -> list[dict]:
        """GET /chat/findChats/<instance>"""
        result = self._request("GET", f"/chat/findChats/{instance_name}")
        return result if isinstance(result, list) else []

    def fetch_messages(self, instance_name: str, remote_jid: str, count: int = 20) -> dict:
        """POST /chat/findMessages/<instance>"""
        return self._request("POST", f"/chat/findMessages/{instance_name}", body={
            "where": {"key": {"remoteJid": remote_jid}},
            "limit": count,
        })

    # ── Groups ─────────────────────────────────────────────────────────────────

    def create_group(
        self, instance_name: str, subject: str, participants: list[str]
    ) -> dict:
        """POST /group/create/<instance>"""
        return self._request("POST", f"/group/create/{instance_name}", body={
            "subject": subject,
            "participants": [p.lstrip("+") for p in participants],
        })

    def fetch_groups(self, instance_name: str, get_participants: bool = False) -> list[dict]:
        """GET /group/fetchAllGroups/<instance>"""
        path = f"/group/fetchAllGroups/{instance_name}"
        if get_participants:
            path += "?getParticipants=true"
        result = self._request("GET", path)
        return result if isinstance(result, list) else []

    # ── Settings ───────────────────────────────────────────────────────────────

    def get_settings(self, instance_name: str) -> dict:
        """GET /settings/find/<instance>"""
        return self._request("GET", f"/settings/find/{instance_name}")

    def update_settings(self, instance_name: str, settings: dict) -> dict:
        """POST /settings/set/<instance>"""
        return self._request("POST", f"/settings/set/{instance_name}", body=settings)



