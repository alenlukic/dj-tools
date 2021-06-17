class QueuedAttempt:
    """ Encapsulates a queued retry attempt. """

    def __init__(self, data):
        self.data = data
        self.attempts = 0


class RetryHandler:
    """ Generic retry handler. """

    def __init__(self, max_retries=3):
        self.max_retries = max_retries
        self.retry_queue = {}
        self.active_items = 0

    def add_attempt(self, key, data=None):
        if key in self.retry_queue:
            return

        print('Adding %s to retry queue' % key)

        self.retry_queue[key] = QueuedAttempt(data)
        self.active_items += 1

    def add_attempts(self, items):
        for key, data in items.items():
            self.add_attempt(key, data)

    def get_pending_attempts(self):
        if self.active_items == 0:
            return {}

        to_process = {}
        for key, attempt in self.retry_queue.items():
            if attempt.attempts == self.max_retries:
                continue

            to_process[key] = attempt.data

            attempt.attempts += 1
            if attempt.attempts == self.max_retries:
                self.active_items -= 1

        return to_process

    def has_pending_attempts(self):
        return self.active_items > 0
