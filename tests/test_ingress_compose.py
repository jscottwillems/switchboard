"""Opt-in HTTPS ingress stays off the default compose file and off the data plane."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COMPOSE = ROOT / "docker-compose.yml"
INGRESS_COMPOSE = ROOT / "docker-compose.ingress.yml"
ROUTES = ROOT / "deploy" / "ingress" / "routes.caddy"
README = ROOT / "README.md"
SECURITY = ROOT / "docs" / "SECURITY.md"
NGINX = ROOT / "apps" / "dashboard" / "nginx.conf"

LOOPBACK_PORTS = {
    "postgres": "127.0.0.1:5432:5432",
    "redis": "127.0.0.1:6379:6379",
    "api": "127.0.0.1:8000:8000",
    "media_gateway": "127.0.0.1:8001:8001",
    "intelligence": "127.0.0.1:8002:8002",
    "dashboard": "127.0.0.1:5173:80",
}


def _services(text: str) -> dict[str, str]:
    """Map each compose service name to its indented body."""

    services: dict[str, str] = {}
    current: str | None = None
    body: list[str] = []
    in_services = False
    for line in text.splitlines():
        if line.startswith("services:"):
            in_services = True
            continue
        if not in_services:
            continue
        if line.startswith("volumes:"):
            break
        if line.startswith("  ") and not line.startswith("    ") and line.endswith(":"):
            if current is not None:
                services[current] = "\n".join(body)
            current = line.strip()[:-1]
            body = []
            continue
        if current is not None:
            body.append(line)
    if current is not None:
        services[current] = "\n".join(body)
    return services


def _active(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.strip().startswith("#"))


def test_default_compose_stays_lan_http() -> None:
    text = DEFAULT_COMPOSE.read_text()
    assert "profiles:" not in text
    assert "cloudflared" not in text
    assert "caddy:" not in text
    assert '"5173:80"' in text
    assert '"5432:5432"' in text
    assert '"6379:6379"' in text
    assert "MEDIA_GATEWAY_PUBLIC_WS: ${MEDIA_GATEWAY_PUBLIC_WS:-ws://localhost:8001/v1/streams}" in text
    assert "SWITCHBOARD_OPERATOR_TOKEN: ${SWITCHBOARD_OPERATOR_TOKEN:-dev-operator-token}" in text
    assert "VITE_OPERATOR_TOKEN: ${SWITCHBOARD_OPERATOR_TOKEN:-dev-operator-token}" in text
    assert "SWITCHBOARD_CORS_ORIGINS: http://localhost:5173" in text
    assert "*" not in text.split("SWITCHBOARD_CORS_ORIGINS", 1)[1].splitlines()[0]


def test_ingress_file_is_opt_in_and_keeps_data_off_the_edge() -> None:
    text = INGRESS_COMPOSE.read_text()
    services = _services(text)
    assert set(services) == {
        "postgres",
        "redis",
        "api",
        "media_gateway",
        "intelligence",
        "dashboard",
        "edge",
        "edge_public",
        "edge_tunnel",
        "tunnel",
        "tunnel_named",
    }
    for name, published in LOOPBACK_PORTS.items():
        body = services[name]
        assert "!override" in body
        assert published in body
        assert "profiles:" not in body
    for name in ("edge", "edge_public"):
        body = services[name]
        assert 'profiles: ["https' in body
        assert '"80:80"' in body
        assert '"443:443"' in body
        assert "5432" not in body
        assert "6379" not in body
        assert "caddy:2.11.4-alpine" in body
    assert 'profiles: ["https"]' in services["edge"]
    assert 'profiles: ["https-public"]' in services["edge_public"]
    tunnel_edge = services["edge_tunnel"]
    assert 'profiles: ["tunnel", "tunnel-named"]' in tunnel_edge
    assert "ports:" not in tunnel_edge
    assert "expose:" in tunnel_edge
    for name in ("tunnel", "tunnel_named"):
        body = services[name]
        assert "ports:" not in body
        assert "cloudflare/cloudflared:2026.9.0" in body
        assert "postgres" not in body
        assert "redis" not in body
        assert "media_gateway" not in body
    assert services["tunnel"].count("tunnel --url http://edge_tunnel:80") == 1
    assert "TUNNEL_TOKEN:" in services["tunnel_named"]
    assert "CLOUDFLARE_TUNNEL_TOKEN" in services["tunnel_named"]
    assert "privileged:" not in text
    assert "network_mode:" not in text
    assert "SWITCHBOARD_CORS_ORIGINS" not in text
    assert "MEDIA_GATEWAY_PUBLIC_WS:" not in text
    joined_upstreams = "\n".join(
        services[name] for name in ("edge", "edge_public", "edge_tunnel", "tunnel", "tunnel_named")
    )
    assert "postgres:" not in joined_upstreams
    assert "redis:" not in joined_upstreams


def test_edge_routes_fail_closed() -> None:
    active = _active(ROUTES.read_text())
    assert "path /v1/internal /v1/internal/* /v1/telephony /v1/telephony/* /v1/streams /v1/streams/*" in active
    assert 'respond "not exposed" 404' in active
    assert "reverse_proxy dashboard:80" in active
    assert "reverse_proxy api:" not in active
    assert "reverse_proxy media_gateway:" not in active
    assert "postgres" not in active
    assert "redis" not in active
    assert "Access-Control-Allow-Origin" not in active
    commented = "\n".join(
        line for line in ROUTES.read_text().splitlines() if line.strip().startswith("#")
    )
    assert "MEDIA_GATEWAY_PUBLIC_WS=wss://<public-host>/v1/streams" in commented
    assert "MEDIA_GATEWAY_PUBLIC_WS=ws://" not in commented


def test_docs_warn_before_a_shared_url() -> None:
    readme = README.read_text()
    security = SECURITY.read_text()
    for text in (readme, security):
        assert "dev-operator-token" in text
        assert "no login screen" in text or "not per-operator login" in text or "not a login" in text
        assert "Vite inlines" in text or "Vite still inlines" in text
        assert "Postgres" in text and "Redis" in text
        assert "wss://" in text
    assert "docker compose up --build" in readme
    assert "COMPOSE_PROFILES=tunnel docker compose -f docker-compose.yml -f docker-compose.ingress.yml up --build" in readme
    assert "COMPOSE_PROFILES=https " in readme
    assert "COMPOSE_PROFILES=https-public " in readme
    assert "SWITCHBOARD_DEV_WEBHOOK_BYPASS" in readme
    nginx = NGINX.read_text()
    assert "$switchboard_forwarded_proto" in nginx
    assert "proxy_set_header X-Forwarded-Proto $scheme;" not in nginx
