def test_health_returns_stable_status(client) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_route_has_consistent_error_shape(client) -> None:
    response = client.get("/api/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_cors_allows_only_the_configured_development_origin(client) -> None:
    allowed = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:4200",
            "Access-Control-Request-Method": "GET",
        },
    )
    rejected = client.options(
        "/api/health",
        headers={
            "Origin": "http://untrusted.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:4200"
    assert rejected.status_code == 400


def test_unhandled_error_does_not_expose_internal_details(client) -> None:
    @client.app.get("/_test/error")
    def raise_for_test() -> None:
        raise RuntimeError("detalle interno de prueba")

    response = client.get("/_test/error")

    assert response.status_code == 500
    assert response.json() == {"detail": "Error interno del servidor."}
