from app.modules.search.service import reciprocal_rank_fusion


def test_reciprocal_rank_fusion_rewards_cross_channel_matches() -> None:
    scores, channels = reciprocal_rank_fusion(
        (
            ("keyword", [1, 2, 3], 0.45),
            ("semantic", [3, 1, 4], 0.55),
        )
    )

    assert scores[1] > scores[2]
    assert scores[3] > scores[4]
    assert channels[1] == ["keyword", "semantic"]
