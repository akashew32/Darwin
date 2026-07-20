from abc import ABC, abstractmethod

from darwin.domain.signal import FeatureVector, Signal


class Strategy(ABC):
    @abstractmethod
    def generate(self, features: FeatureVector) -> Signal: ...
