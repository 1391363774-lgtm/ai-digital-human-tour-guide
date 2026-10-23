from app.services.tts_service import build_viseme_timeline


def test_word_gap_is_not_merged_into_open_mouth():
    events=build_viseme_timeline([{'text':'啊','offset_ms':0,'duration_ms':100},
                                 {'text':'啊','offset_ms':120,'duration_ms':100}],300)
    # Twenty milliseconds of silence must not be merged away.
    assert events[0]['t']+events[0]['d']==100
    assert events[1]['t']==120
