from scoring_template import ScoringTemplate
class WeightedScoringTemplate(ScoringTemplate):

    def __init__(self, description, score_map, weight_map):
        super().__init__(description, score_map)
        self._weight_map = weight_map

    def calculate_weighted(self, key):
        score = self._score_map.get(key, 0)
        weight = self._weight_map.get(key, 0)
        return score * weight