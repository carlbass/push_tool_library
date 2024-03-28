# Author- Carl Bass
# Description- push tool library from the local folder to github

import adsk.core, adsk.fusion, adsk.cam, traceback
import os
import json
import base64

# Global list to keep all event handlers in scope.
handlers = []

# global variables available in all functions
app = adsk.core.Application.get()
ui  = app.userInterface

# global variables because I can't find a better way to pass this info around -- would be nice if fusion api had some cleaner way to do this
debug = False

def run(context):
    
    try:

        # Get the CommandDefinitions collection so we can add a command
        command_definitions = ui.commandDefinitions
        
        tooltip = 'Push tool library to git'

        # Create a button command definition.
        library_button = command_definitions.addButtonDefinition('push_tool_library', 'Push tool library', tooltip, 'resources')
        
        # Connect to the command created event.
        library_command_created = command_created()
        library_button.commandCreated.add (library_command_created)
        handlers.append(library_command_created)

        # add the Moose Tools to the CAM workspace Utilities tab
                
        utilities_tab = ui.allToolbarTabs.itemById('UtilitiesTab')

        if utilities_tab:
            debug_print ('UtilitiesTab found')

            # get or create the "Moose Tools" panel.
        
            moose_cam_panel = ui.allToolbarPanels.itemById('MooseCAM')
            if not moose_cam_panel:
                moose_cam_panel = utilities_tab.toolbarPanels.add('MooseCAM', 'Moose Tools')
                debug_print ('Moose CAM panel created')

        if moose_cam_panel:
            # Add the command to the panel.
            control = moose_cam_panel.controls.addCommand (library_button)
            control.isPromoted = False
            control.isPromotedByDefault = False
            debug_print ('Moose CAM Tools installed')

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

# Event handler for the commandCreated event.
class command_created (adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):

        text_palette = ui.palettes.itemById('TextCommands')

        event_args = adsk.core.CommandCreatedEventArgs.cast(args)
        command = event_args.command
        inputs = command.commandInputs
 
        # Connect to the execute event
        onExecute = command_executed()
        command.execute.add(onExecute)
        handlers.append(onExecute)

        # create the dropdown with all the tool libraries in the github repository
        library_selection_input = inputs.addDropDownCommandInput('tool_library_select', 'Select tool library', adsk.core.DropDownStyles.TextListDropDownStyle)
        library_selection_input.maxVisibleItems = 10
        list = library_selection_input.listItems

        library_manager = adsk.cam.CAMManager.get().libraryManager
        tool_libraries = library_manager.toolLibraries
        tool_library_url = tool_libraries.urlByLocation(adsk.cam.LibraryLocations.LocalLibraryLocation)

        local_libraries = tool_libraries.childAssetURLs(tool_library_url)
        
        for ll in local_libraries:
            debug_print (f'{ll.toString()}')
            basename = os.path.basename(ll.toString())
            list.add (basename, False, '')

        # create debug checkbox widget
        inputs.addBoolValueInput('debug', 'Debug', True, '', debug)

# Event handler for the execute event.
class command_executed (adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        global debug

        try:

            # get current command
            command = args.firingEvent.sender

            for input in command.commandInputs:
                if (input.id == 'tool_library_select'):
                    library_selected = input.selectedItem
                    debug_print (f'<{library_selected.name}>')
                elif (input.id == 'debug'):
                    debug = input.value           
                else: 
                    debug_print (f'OOOPS --- too much input')


            # find the library selected
            library_manager = adsk.cam.CAMManager.get().libraryManager
            tool_libraries = library_manager.toolLibraries

            # look in local libraries and append the selected library name to the URL
            tool_library_url = tool_libraries.urlByLocation(adsk.cam.LibraryLocations.LocalLibraryLocation)
            tool_library_url = tool_library_url.join (library_selected.name)

            selected_tool_library = tool_libraries.toolLibraryAtURL(tool_library_url)

            # turn the local tool library into JSON
            file_contents = selected_tool_library.toJson()       

            # now find the file in git so we can get the sha value which is needed to update

            repo_url = 'https://api.github.com/repos/carlbass/fusion_tool_libraries/contents/' + library_selected.name + '.json'
            repo_url = repo_url.replace (' ', '%20')
            debug_print (f'<{repo_url}>')

            request = adsk.core.HttpRequest.create(repo_url, adsk.core.HttpMethods.GetMethod)
            request.setHeader ('accept', 'application/vnd.github+json')
            response = request.executeSync()

            if response.statusCode == 200:
                jdata = json.loads(response.data)
    
                if jdata:
                    selected_sha = jdata ['sha']
                    debug_print (f'sha = {selected_sha}')

            github_token = os.getenv ('GITHUB_TOKEN')
            debug_print  (f'token = {github_token}')

            github_token_string = f'Bearer {github_token}'
            debug_print (f'token string = {github_token_string}')

            json_request_data = {
                "message": "tool library push",
                "content": base64.b64encode(file_contents.encode()).decode(),
                "sha": selected_sha
                }
        
            json_request_string = json.dumps (json_request_data)

            put_url = 'https://api.github.com/repos/carlbass/fusion_tool_libraries/contents/' + library_selected.name + '.json'
            put_url = put_url.replace (' ', '%20')
            put_request = adsk.core.HttpRequest.create(put_url, adsk.core.HttpMethods.PutMethod)
            put_request.data = json_request_string
        
            put_request.setHeader ('accept', 'application/vnd.github+json')
            put_request.setHeader ('Authorization', github_token_string)
        
            put_response = put_request.executeSync()

            debug_print (f'put response code: {put_response.statusCode}')

            response_json = json.loads(put_response.data)
            debug_print (f'put response: {response_json}')
    
        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


def debug_print (msg):
    if debug:
        text_palette = ui.palettes.itemById('TextCommands')
        text_palette.writeText (msg)

def stop(context):
    try:
        global handlers

        # Clean up the UI.
        command_definitions = ui.commandDefinitions.itemById('push_tool_library')
        if command_definitions:
            command_definitions.deleteMe()
        
        # get rid of this button
        moose_cam_panel = ui.allToolbarPanels.itemById('MooseCAM')

        control = moose_cam_panel.controls.itemById('push_tool_library')
        if control:
            control.deleteMe()

        # and if it's the last button, get rid of the moose panel
        if moose_cam_panel.controls.count == 0:
            moose_cam_panel.deleteMe()
        
        handlers = []

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))	