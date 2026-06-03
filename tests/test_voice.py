from zero.voice import split_sentences

def test_split_sentences():
    assert split_sentences("Hello, Ahmad. All systems online! Ready?") == \
        ["Hello, Ahmad.", "All systems online!", "Ready?"]
