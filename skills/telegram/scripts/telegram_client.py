#!/usr/bin/env python3
"""
telegram_client.py — Wrapper Python para Telegram Bot API.

Referência: https://core.telegram.org/bots/api
Auth: Bearer token no path da URL: https://api.telegram.org/bot<TOKEN>/<METHOD>
"""
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional


class TelegramClient:
    """
    Cliente HTTP de baixo nível para a Telegram Bot API.

    Uso:
        client = TelegramClient(token="123456789:AAH...")
        client.get_me()
        client.set_webhook(url="https://...", secret_token="abc")
        client.send_message(chat_id="123", text="Olá!")
    """

    BASE_URL = "https://api.telegram.org"

    def __init__(self, token: str):
        self.token = token
        self._base = f"{self.BASE_URL}/bot{token}"

    def _request(self, method: str, http_method: str = "GET",
                 body: Optional[dict] = None, timeout: int = 20) -> Any:
        url = f"{self._base}/{method}"
        data = json.dumps(body, default=str).encode("utf-8") if body else None
        headers = {"Content-Type": "application/json"} if data else {}
        req = urllib.request.Request(url, data=data, headers=headers, method=http_method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                result = json.loads(raw)
                if not result.get("ok"):
                    raise RuntimeError(f"Telegram error: {result.get('description', raw[:200])}")
                return result.get("result")
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"HTTP {e.code} {method}: {body_text}") from e

    # ── Bot info ───────────────────────────────────────────────────────────────

    def get_me(self) -> dict:
        """GET /getMe → informações do bot (id, username, name)."""
        return self._request("getMe")

    # ── Webhook ────────────────────────────────────────────────────────────────

    def set_webhook(
        self,
        url: str,
        secret_token: str = "",
        allowed_updates: Optional[list] = None,
        drop_pending_updates: bool = False,
        max_connections: int = 40,
    ) -> bool:
        """POST /setWebhook → registra URL de webhook."""
        payload: dict = {
            "url": url,
            "max_connections": max_connections,
            "drop_pending_updates": drop_pending_updates,
        }
        if secret_token:
            payload["secret_token"] = secret_token
        if allowed_updates:
            payload["allowed_updates"] = allowed_updates
        result = self._request("setWebhook", "POST", payload)
        return bool(result)

    def delete_webhook(self, drop_pending_updates: bool = False) -> bool:
        """POST /deleteWebhook → remove webhook registrado."""
        result = self._request("deleteWebhook", "POST",
                               {"drop_pending_updates": drop_pending_updates})
        return bool(result)

    def get_webhook_info(self) -> dict:
        """GET /getWebhookInfo → informações do webhook atual."""
        return self._request("getWebhookInfo") or {}

    # ── Mensagens ──────────────────────────────────────────────────────────────

    def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = "Markdown",
        reply_to_message_id: Optional[int] = None,
        disable_notification: bool = False,
    ) -> dict:
        """POST /sendMessage → envia mensagem de texto."""
        payload: dict = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_notification": disable_notification,
        }
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id
        return self._request("sendMessage", "POST", payload) or {}

    def send_chat_action(self, chat_id: str, action: str = "typing") -> bool:
        """POST /sendChatAction → ex: 'typing' enquanto Marcos processa."""
        result = self._request("sendChatAction", "POST",
                               {"chat_id": chat_id, "action": action})
        return bool(result)

    def send_photo(self, chat_id: str, photo_url: str, caption: str = "") -> dict:
        """POST /sendPhoto → envia foto por URL."""
        payload: dict = {"chat_id": chat_id, "photo": photo_url}
        if caption:
            payload["caption"] = caption
        return self._request("sendPhoto", "POST", payload) or {}

    def send_document(self, chat_id: str, doc_url: str, caption: str = "") -> dict:
        """POST /sendDocument → envia documento por URL."""
        payload: dict = {"chat_id": chat_id, "document": doc_url}
        if caption:
            payload["caption"] = caption
        return self._request("sendDocument", "POST", payload) or {}

    def edit_message_text(self, chat_id: str, message_id: int, text: str,
                          parse_mode: str = "Markdown") -> dict:
        """POST /editMessageText → edita texto de mensagem existente."""
        return self._request("editMessageText", "POST", {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode,
        }) or {}

    def delete_message(self, chat_id: str, message_id: int) -> bool:
        """POST /deleteMessage → apaga mensagem."""
        result = self._request("deleteMessage", "POST",
                               {"chat_id": chat_id, "message_id": message_id})
        return bool(result)

    # ── Updates (polling — para testes sem webhook) ────────────────────────────

    def get_updates(self, offset: int = 0, limit: int = 100, timeout: int = 0) -> list:
        """GET /getUpdates → polling de mensagens (não usar com webhook ativo)."""
        return self._request("getUpdates", "GET") or []

    # ── Chat info ──────────────────────────────────────────────────────────────

    def get_chat(self, chat_id: str) -> dict:
        """POST /getChat → informações do chat."""
        return self._request("getChat", "POST", {"chat_id": chat_id}) or {}

    def get_chat_member(self, chat_id: str, user_id: int) -> dict:
        """POST /getChatMember → informações de membro."""
        return self._request("getChatMember", "POST",
                             {"chat_id": chat_id, "user_id": user_id}) or {}

    # ── Commands ───────────────────────────────────────────────────────────────

    def set_my_commands(self, commands: list) -> bool:
        """POST /setMyCommands → define lista de comandos do bot."""
        result = self._request("setMyCommands", "POST", {"commands": commands})
        return bool(result)

    def delete_my_commands(self) -> bool:
        """POST /deleteMyCommands → remove todos os comandos."""
        result = self._request("deleteMyCommands", "POST", {})
        return bool(result)

    # ── Inline ─────────────────────────────────────────────────────────────────

    def answer_callback_query(self, callback_query_id: str, text: str = "") -> bool:
        """POST /answerCallbackQuery → responde a botões inline."""
        result = self._request("answerCallbackQuery", "POST", {
            "callback_query_id": callback_query_id,
            "text": text,
        })
        return bool(result)
