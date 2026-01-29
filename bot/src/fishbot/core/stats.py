import json

class StatsTracker:
    def __init__(self):
        self.stats = {
            'cycles': 0,
            'fish_caught': 0,
            'fish_escaped': 0,
            'rod_breaks': 0,
            'timeouts': 0
        }
        # Flag para saber se houve mudanca desde o ultimo envio
        self._changed = True

    def increment(self, stat_name, value=1):
        if stat_name in self.stats:
            self.stats[stat_name] += value
            self._changed = True

    def get_json(self):
        """Retorna as estatisticas em formato JSON string se houver mudancas."""
        if self._changed:
            self._changed = False
            return json.dumps({"type": "STATS_UPDATE", "data": self.stats})
        return None

    def show(self):
        # Mantemos o show original para debugging no terminal se necessario
        print("\n" + "=" * 50)
        print("📊 STATISTICS")
        print("=" * 50)
        for stat, value in self.stats.items():
            title = stat.replace('_', ' ').replace('cycles', 'Cycles completed').capitalize()
            print(f"  {title}: {value}")
        print("=" * 50)