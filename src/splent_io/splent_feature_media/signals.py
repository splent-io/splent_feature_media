"""
Signals for splent_feature_media.

Use ``define_signal`` to declare signals this feature emits.
Use ``connect_signal`` to listen to signals from other features.

Examples::

    # Define a signal (this feature emits it):
    from splent_framework.signals.signal_utils import define_signal
    item_created = define_signal("item-created", "splent_feature_media")

    # Connect to a signal from another feature:
    from splent_framework.signals.signal_utils import connect_signal

    @connect_signal("user-registered", "splent_feature_media")
    def on_user_registered(sender, user, **kwargs):
        pass
"""
