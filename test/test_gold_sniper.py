import pytest
from unittest.mock import AsyncMock, MagicMock
import main
from datetime import datetime

@pytest.fixture(autouse=True)
def reset_globals():
    main.SEUILS_MANUELS = []
    main.DERNIERE_MAJ_HORAIRES.clear()
    main.DERNIER_SEUIL_CASSE = None
    main.COMPTEUR_APRES_CASSURE = 0
    yield

# --- 1. Chargement des seuils ---
def test_charger_seuils_depuis_notion_mock(monkeypatch):
    mock_query = lambda **kwargs: {
        "results": [
            {"properties": {"Valeur": {"number": 3300}, "Type": {"select": {"name": "support"}}}},
            {"properties": {"Valeur": {"number": 3350}, "Type": {"select": {"name": "pivot"}}}},
            {"properties": {"Valeur": {"number": 3400}, "Type": {"select": {"name": "résistance"}}}},
        ]
    }
    monkeypatch.setattr(main.notion.databases, "query", mock_query)
    main.SEUILS_MANUELS = []
    main.charger_seuils_depuis_notion()
    noms = [s["nom"] for s in main.SEUILS_MANUELS]
    assert "Pivot" in noms
    assert "R1" in noms
    assert "S1" in noms

# --- 2. Calcul automatique des seuils ---
def test_calcul_pivots():
    high = 3400
    low = 3300
    close = 3350
    pivot = round((high + low + close) / 3, 2)
    r1 = round(2 * pivot - low, 2)
    s1 = round(2 * pivot - high, 2)
    assert pivot == 3366.67
    assert r1 == 3433.33
    assert s1 == 3300.0

# --- 5. Blocage des notifications ---
def test_blocage_notifications():
    main.DERNIER_SEUIL_CASSE = "R1"
    main.COMPTEUR_APRES_CASSURE = 4
    main.SEUILS_MANUELS = [{"valeur": 3400, "type": "résistance", "nom": "R1"}]
    signal_type = None
    price = 3401
    if price > 3400 + 0.5:
        if main.COMPTEUR_APRES_CASSURE >= 5:
            signal_type = "📈 Cassure R1 +1$ 🚧"
        else:
            signal_type = "📈 Cassure R1 +1$"
            main.COMPTEUR_APRES_CASSURE += 1
    assert signal_type == "📈 Cassure R1 +1$"
    assert main.COMPTEUR_APRES_CASSURE == 5

# --- 6. Réinitialisation après changement de seuil ---
def test_reset_compteur():
    main.DERNIER_SEUIL_CASSE = "R1"
    main.COMPTEUR_APRES_CASSURE = 5
    new_seuil = "R2"
    if new_seuil != main.DERNIER_SEUIL_CASSE:
        main.DERNIER_SEUIL_CASSE = new_seuil
        main.COMPTEUR_APRES_CASSURE = 1
    assert main.COMPTEUR_APRES_CASSURE == 1

# --- 7. SL et SL suiveur ---
def test_sl_suiveur():
    seuil = 3300
    last_price = 3305
    sl = round(seuil - 1, 2)
    sl_suiv = round(last_price + 5, 2)
    assert sl == 3299.0
    assert sl_suiv == 3310.0

# --- 8. Cas anormal : pas de seuils ---
def test_aucun_seuil():
    main.SEUILS_MANUELS = []
    try:
        pivot = next((s["valeur"] for s in main.SEUILS_MANUELS if s["nom"] == "Pivot"), None)
        assert pivot is None
    except Exception as e:
        pytest.fail(f"Erreur inattendue : {e}")

# --- 4. Mock complet de fetch_gold_data ---
import pytest
@pytest.mark.asyncio
async def test_fetch_gold_data_mock(monkeypatch):
    main.SEUILS_MANUELS = [
        {"valeur": 3400, "type": "résistance", "nom": "R1"},
        {"valeur": 3350, "type": "pivot", "nom": "Pivot"},
        {"valeur": 3300, "type": "support", "nom": "S1"},
    ]

    monkeypatch.setattr(main.notion.pages, "create", lambda **kwargs: print("✅ Notion call mock"))

    class MockResponse:
        def raise_for_status(self): pass
        def json(self):
            return {"results": [{"c": 3401, "v": 1250}]}

    async def mock_get(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(main.httpx.AsyncClient, "get", mock_get)

    await main.fetch_gold_data()
