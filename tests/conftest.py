import os

from hypothesis import settings

settings.register_profile("default", max_examples=1000)
settings.register_profile("auto", max_examples=20)
profile = os.environ.get("JAMA_PROFILE", "default")
settings.load_profile(profile)
