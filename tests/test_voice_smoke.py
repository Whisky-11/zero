import pytest
from zero.voice import Voice

@pytest.mark.manual
def test_voice_speaks():
    Voice().speak("Good evening, Ahmad. Zero online.")
