/*
 * View model for OctoPrint-Tinamous
 *
 * Author: Stephen Harrison
 * License: AGPLv3
 */
$(function() {
    function TinamousViewModel(parameters) {
        var self = this;

        // assign the injected parameters, e.g.:
        // self.loginStateViewModel = parameters[0];
        // self.settingsViewModel = parameters[1];

        // TODO: Implement your plugin's view model here.
    }

    // view model class, parameters for constructor, container to bind to
    OCTOPRINT_VIEWMODELS.push([
        TinamousViewModel,

        // e.g. loginStateViewModel, settingsViewModel, ...
        [ /* "loginStateViewModel", "settingsViewModel" */ ],

        // e.g. #settings_plugin_tinamous, #tab_plugin_tinamous, ...
        [ /* ... */ ]
    ]);
});
