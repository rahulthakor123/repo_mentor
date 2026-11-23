FEATURES: dict[str, type] = {}


def register(cls):
    FEATURES[cls.name] = cls
    return cls