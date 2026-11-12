import pandas as pd

from modules.data_cleaner import clean_records
from modules.followers_analyzer import AGE_GROUPS, add_follow_age, compare_accounts


def _clean(users, dates=None):
    dates = dates or ["2025-01-01"] * len(users)
    frame = pd.DataFrame(
        {
            "numero_lista": range(1, len(users) + 1),
            "usuario": users,
            "perfil": [f"https://www.instagram.com/{u.lstrip('@')}" for u in users],
            "fecha": dates,
        }
    )
    return clean_records(frame).data


def test_identifies_mutual_and_both_non_mutual_directions():
    result = compare_accounts(
        _clean(["Mutuo", "solo_me_sigue"]),
        _clean(["@mutuo", "solo_no_me_sigue"]),
        as_of=pd.Timestamp("2025-01-20"),
    )

    assert result.summary == {
        "seguidores": 2,
        "seguidos": 2,
        "mutuos": 1,
        "no_me_siguen": 1,
        "no_sigo_de_regreso": 1,
    }
    assert result.mutual["usuario_normalizado"].tolist() == ["mutuo"]
    assert result.not_following_back["usuario_normalizado"].tolist() == [
        "solo_no_me_sigue"
    ]
    assert result.not_followed_back["usuario_normalizado"].tolist() == [
        "solo_me_sigue"
    ]
    assert (
        result.summary["mutuos"] + result.summary["no_me_siguen"]
        == result.summary["seguidos"]
    )
    assert (
        result.summary["mutuos"] + result.summary["no_sigo_de_regreso"]
        == result.summary["seguidores"]
    )


def test_age_groups_have_non_overlapping_boundaries_and_keep_invalid_dates_unknown():
    frame = pd.DataFrame(
        {
            "fecha": [
                "2025-01-01",
                "2024-12-02",
                "2024-07-05",
                "2024-01-21",
                "2024-01-01",
                "2025-01-21",
                "not a date",
            ]
        }
    )

    result = add_follow_age(frame, as_of=pd.Timestamp("2025-01-20"))

    assert result["antiguedad"].astype(str).tolist() == [
        AGE_GROUPS[0],
        AGE_GROUPS[1],
        AGE_GROUPS[2],
        AGE_GROUPS[2],
        AGE_GROUPS[3],
        AGE_GROUPS[4],
        AGE_GROUPS[4],
    ]
    assert result.loc[5, "dias_transcurridos"] == -1
    assert pd.isna(result.loc[6, "dias_transcurridos"])
