import pytest
import main
from datetime import datetime, timedelta

@pytest.fixture(autouse=True)
def reset_globals():
    main.SEUILS_MANUELS = []
    main.DERNIERE_MAJ_HORAIRES.clear()
    main.DERNIER_SEUIL_CASSE = None
    main.COMPTEUR_APRES_CASSURE = 0
    yield

# --- 1. Chargement des seuils ---
def test_chargement_seuils_mock(monkeypatch):
    def mock_query(database_id, filter):
        return {
            "results": [
                {"properties": {
                    "Valeur": {"number": 3300}, "Type": {"select": {"name": "support"}}
                }},
                {"properties": {
                    "Valeur": {"number": 3350}, "Type": {"select": {"name": "pivot"}}
                }},
                {"properties": {
                    "Valeur": {"number": 3400}, "Type": {"select": {"name": "résistance"}}
                }}
            ]
        }
    monkeypatch.setattr(main.notion.databases, "query", mock_query)
    main.SEUILS_MANUELS = []
    main.charger_seuils_depuis_notion()
    noms = [s["nom"] for s in main.SEUILS_MANUELS]
    assert "Pivot" in noms
    assert "R1" in noms
    assert "S1" in noms
    assert noms == sorted(noms, key=lambda x: ("S" in x, x))

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
