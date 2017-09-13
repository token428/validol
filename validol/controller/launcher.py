import pip
import traceback

from validol.model.launcher import ModelLauncher
from validol.view.launcher import ViewLauncher
from validol.model.store.view.view_flavor import ViewFlavor
from validol.setup import SETUP_CONFIG


class ControllerLauncher:
    def __init__(self):
        self.model_launcher = ModelLauncher(self).init_data()

        self.view_launcher = ViewLauncher(self, self.model_launcher)

        self.view_launcher.event_loop()

    def update_data(self, how):
        return self.model_launcher.update(how)

    def draw_table(self, table_pattern, actives):
        try:
            df = self.model_launcher.prepare_tables(table_pattern, actives)
        except Exception:
            self.view_launcher.display_error(
                'Table evaluation failed',
                'Something badly wrong happened while atoms evaluation. '
                'Here is the stack trace: \n{}'.format(traceback.format_exc()))

            return

        title = ViewFlavor.show_ais(actives, self.model_launcher)

        for i, labels in enumerate(table_pattern.formula_groups):
            self.view_launcher.show_table(df, labels, title)

        self.view_launcher.show_graph_dialog(df, table_pattern, title)

        self.view_launcher.refresh_prices()

    def draw_graph(self, df, pattern, table_labels, title):
        self.view_launcher.show_graph(df, pattern, table_labels, title)

    def refresh_tables(self):
        self.view_launcher.refresh_tables()

    def refresh_actives(self):
        self.view_launcher.refresh_actives()

    def show_table_dialog(self):
        self.view_launcher.show_table_dialog()

    def show_pdf_helper_dialog(self, processors, widgets):
        return self.view_launcher.show_pdf_helper_dialog(processors, widgets)

    def get_chosen_actives(self):
        return self.view_launcher.get_chosen_actives()

    def ask_name(self):
        return self.view_launcher.ask_name()

    def edit_pattern(self, json_str):
        return self.view_launcher.edit_pattern(json_str)

    def show_main_window(self):
        self.view_launcher.show_main_window()

    def on_main_window_close(self):
        self.view_launcher.on_main_window_close()

    def quit(self):
        self.view_launcher.quit()

    def notify_update(self, results):
        self.view_launcher.notify_update(results)

    def notify(self, message):
        self.view_launcher.notify(message)

    def refresh_schedulers(self):
        self.view_launcher.refresh_schedulers()

    def show_scheduler_dialog(self):
        self.view_launcher.show_scheduler_dialog()

    def mark_update_required(self):
        self.view_launcher.mark_update_required()

    def get_package_config(self):
        return SETUP_CONFIG

    def pip_update(self):
        pip.main(['install', '--extra-index-url', 'https://pypi.python.org/pypi', '--upgrade', 'validol'])
        self.quit()

    def current_pip_version(self):
        return self.get_package_config()['version']