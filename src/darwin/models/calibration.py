from sklearn.calibration import CalibratedClassifierCV


def calibrate_prefit(model: object) -> CalibratedClassifierCV:
    return CalibratedClassifierCV(model, cv="prefit", method="isotonic")
