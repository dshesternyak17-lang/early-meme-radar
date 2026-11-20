
import json
import os
import requests
from datetime import datetime, timezone

from bot import send_message

NETWORKS = {
    "solana": "Solana",
    "base": "Base",
    "bsc": "BNB Chain",
    "eth": "Ethereum"
}

API = "https://api.geckoterminal.com/api/v2"
STATE_FILE = "seen_pools.json"

def load_seen():
    try:
        with open(STATE_FILE, "r") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def save_seen(seen):
    with open(STATE_FILE, "w") as f:
        json.dump(list(seen)[-2000:], f)

def scan():
    seen = load_seen()
    updated = set(seen)

    for network, network_name in NETWORKS.items():
        try:
            response = requests.get(
                f"{API}/networks/{network}/new_pools",
                params={"include": "base_token"},
                headers={"Accept": "application/json;version=20230302"},
                timeout=20
            )
            response.raise_for_status()
            result = response.json()

            included = {
                item["id"]: item.get("attributes", {})
                for item in result.get("included", [])
                if item.get("type") == "token"
            }

            for pool in result.get("data", []):
                pool_id = pool.get("id", "")
                if not pool_id or pool_id in seen:
                    continue

                attrs = pool.get("attributes", {})
                relationships = pool.get("relationships", {})
                token_ref = relationships.get("base_token", {}).get("data", {})
                token = included.get(token_ref.get("id", ""), {})

                name = token.get("name", "Unknown")
                symbol = token.get("symbol", "?")
                address = token.get("address", "")

                liquidity = float(attrs.get("reserve_in_usd") or 0)
                volume = float(
                    (attrs.get("volume_usd") or {}).get("h24") or 0
                )

                created = attrs.get("pool_created_at")
                if created:
                    created_at = datetime.fromisoformat(
                        created.replace("Z", "+00:00")
                    )
                    age = (
                        datetime.now(timezone.utc) - created_at
                    ).total_seconds() / 60
                    if age > 15 or age < 0:
                        continue

                if liquidity < 1000:
                    continue

                link = (
                    f"https://www.geckoterminal.com/"
                    f"{network}/pools/{pool_id.split('_')[-1]}"
                )

                message = (
                    f"🆕 НОВЫЙ ПУЛ — {network_name}\n\n"
                    f"Токен: {name} ({symbol})\n"
                    f"Ликвидность: ${liquidity:,.0f}\n"
                    f"Объём 24ч: ${volume:,.0f}\n"
                    f"Адрес: {address}\n\n"
                    f"График: {link}\n"
                    f"⚠️ Проверь риски перед покупкой."
                )

                send_message(message)
                updated.add(pool_id)

        except Exception as error:
            print(f"{network_name}: {error}")

    save_seen(updated)

if __name__ == "__main__":
    scan()
