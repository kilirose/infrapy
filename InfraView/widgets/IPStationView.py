import os

from PyQt5.QtWidgets import (QLabel, QHBoxLayout, QCheckBox, QDialogButtonBox,
                             QPushButton, QWidget, QTextEdit, QTabWidget, QFileDialog,
                             QVBoxLayout, QSplitter, QDialog)

from PyQt5.QtGui import QIcon, QFont

from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QDir, QSettings

import obspy
from obspy import read_inventory
from obspy.core.inventory import Inventory

from InfraView.widgets import IPStationMatchDialog
from InfraView.widgets import IPUtils

import pyqtgraph as pg


class IPStationView(QWidget):

    ''' Widget that shows pertinent information about the current inventory.
        Note that this widget does not keep a copy of the current inventory, that
        is stored in the parent waveformwidget.  This widget simply gets and puts inventory 
        info from there.
    '''

    savefile = None

    inventory_changed = pyqtSignal(Inventory)
    sig_inventory_cleared = pyqtSignal()

    def __init__(self, parent):
        super().__init__()

        self.parent = parent

        self.inv = None

        self.buildUI()
        
        self.show()

    def buildUI(self):

        self.buildIcons()

        self.station_TabWidget = QTabWidget()
        self.station_TabWidget.setMinimumSize(200,0)
        self.station_TabWidget.setTabsClosable(True)
        self.station_TabWidget.tabCloseRequested.connect(self.remove_station_from_inv)
        # self.station_TabWidget.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)

        self.arrayViewWidget = IPArrayView(self)
        self.arrayViewWidget.setMinimumSize(200, 0)

        self.clearButton = QPushButton('Clear')
        button_font = self.clearButton.font()
        button_font.setPointSize(10)
        self.clearButton.setFont(button_font)
        self.clearButton.setIcon(self.clearIcon)

        self.saveButton = QPushButton('Save')
        self.saveButton.setIcon(self.saveIcon)
        self.saveButton.setFont(button_font)

        self.saveAsButton = QPushButton('Save As...')
        self.saveAsButton.setIcon(self.saveAsIcon)
        self.saveAsButton.setFont(button_font)

        self.loadButton = QPushButton('Load...')
        self.loadButton.setFont(button_font)
        self.loadButton.setIcon(self.openIcon)

        self.reconcileButton = QPushButton('Reconcile...')
        self.reconcileButton.setFont(button_font)
        self.reconcileButton.setToolTip(self.tr('Attempt to download stations for current waveforms'))

        savebuttonLayout = QVBoxLayout()

        savebuttonLayout.addWidget(self.loadButton)
        savebuttonLayout.addWidget(self.clearButton)
        savebuttonLayout.addWidget(self.saveButton)
        savebuttonLayout.addWidget(self.saveAsButton)
        savebuttonLayout.addWidget(self.reconcileButton)
        savebuttonLayout.addStretch()

        mainHSplitter = QSplitter(Qt.Horizontal)
        mainHSplitter.setStyleSheet("QSplitter::handle{ background-color: #DDD}")

        mainHSplitter.addWidget(self.station_TabWidget)
        mainHSplitter.addWidget(self.arrayViewWidget)

        mainHSplitter.setSizes([100000,100000])

        mainLayout = QHBoxLayout()
        mainLayout.addWidget(mainHSplitter)
        mainLayout.addLayout(savebuttonLayout)

        # go ahead and make an instance of the matchDialog for later use
        self.matchDialog = IPStationMatchDialog.IPStationMatchDialog(self)

        self.setLayout(mainLayout)

        self.duplicate_sta_dialog = IPDuplicateStationDialog(self)

        self.connectSignalsandSlots()

    def buildIcons(self):
        self.clearIcon = QIcon.fromTheme("edit-clear")
        self.openIcon = QIcon.fromTheme("document-open")
        self.saveIcon = QIcon.fromTheme("document-save")
        self.saveAsIcon = QIcon.fromTheme("document-save-as")

    def connectSignalsandSlots(self):
        self.clearButton.clicked.connect(self.clear_all)
        self.saveButton.clicked.connect(self.saveStations)
        self.saveAsButton.clicked.connect(self.saveStationsAs)
        self.loadButton.clicked.connect(self.loadStations)
        self.reconcileButton.clicked.connect(self.reconcileStations)

        self.inventory_changed.connect(self.arrayViewWidget.set_data)
        self.sig_inventory_cleared.connect(self.arrayViewWidget.clear)

    def get_inventory(self):
        return self.inv

    def populateTextEdit(self, te, sta, net_code):
        ''' This is the code that generates the text that describes a station and its channels
        te is the QTextEdit we are editing. Note that these are created on the fly, that's why the ref needs to be passed
        sta is the station we are writing about
        net_code is the network code for this particular stations network
        '''
        html_str = ""
        html_str += "<b>Network:</b> " + net_code + "<br>"
        html_str += "<b>Station:</b> " + sta.code + "<ol>"
        sta_dictionary = {
            'Latitude': sta.latitude,
            'Longitude': sta.longitude,
            'Elevation': sta.elevation,
            'Creation Date': sta.creation_date,
            'Termination Date': sta.termination_date,
            'Historical Code': sta.historical_code, 
            'Total Number of Channels': len(sta.channels)
        }
        for sta_k, sta_v in sta_dictionary.items():
            # loop through the dictionary and combine the key/values
            html_str += "<li>" +  sta_k + ": " + str(sta_v) + "</li>"
        html_str += "</ul>"

        for chan in sta.channels:
            html_str += '<b>Channel:</b> ' + chan.code + '<ul>'
            ch_dictionary = {
                'Latitude': chan.latitude,
                'Longitude': chan.longitude,
                'Elevation': chan.elevation,
                'Sample Rate': chan.sample_rate,
                'Location Code:': chan.location_code,
                'Sensor': chan.sensor,
                'Start Date': chan.start_date,
                'End Date': chan.end_date 
            }
            for ch_k, ch_v in ch_dictionary.items():
                # loop through the dictionary and combine the key/values
                html_str += "<li>" +  ch_k + ": " + str(ch_v) + "</li>"
            html_str += "</ul>"
                 
        te.setHtml(html_str)

    def update_station_view(self):
        # populate the station tabs in the Station view
        self.clear_view()

        # Create the Tabs, and fill with metadata
        for network in self.inv:
            for station in network:
                newTextEdit = QTextEdit()
                self.populateTextEdit(newTextEdit, station, network.code)
                self.station_TabWidget.addTab(newTextEdit, network.code + '.' + station.code)

        # Signal to the array viewer to update
        self.inventory_changed.emit(self.inv)

    def getStationCount(self):

        if self.inv is None:
            return 0
        cnt = 0
        for network in self.inv.networks:
            for station in network.stations:
                cnt += 1
        return cnt

    def clear_view(self):

        for i in range(self.station_TabWidget.count()):
            self.station_TabWidget.removeTab(0)

        # now signal to the application that the inventory needs to be cleared
        
    def clear_inv(self):
        # resets inv to None
        self.inv = None
        self.sig_inventory_cleared.emit()

    def clear_all(self):
        self.clear_view()
        self.clear_inv()

    @pyqtSlot(int)
    @pyqtSlot(str)
    def remove_station_from_inv(self, entry):
        # you can pass either a tab index, or a trace.id.  
        if type(entry) is int:
            # get the name of the tab
            sta_name = self.station_TabWidget.tabText(entry).split('.')[1]

        else:
            sta_name = entry.split('.')[1]

        self.inv = self.inv.remove(station=sta_name)
        
        self.update_station_view()

    

    def saveStations(self):
    
        # if there is no current filename, prompt for one...
        # TODO: if there is an open project, default to that
        if self.savefile is None:
            self.saveStationsAs()
        else:
            if self.inv is None:
                IPUtils.errorPopup('Oh my... There are no stations to save')
                return
            self.inv.write(self.savefile[0], format='stationxml', validate=True)
            path = os.path.dirname(self.savefile[0])
            settings = QSettings('LANL', 'InfraView')
            settings.setValue("last_stationfile_directory", path)

    def saveStationsAs(self):
        print(self.x)
        if self.inv is None:
            IPUtils.errorPopup('Oops... There are no stations to save')
            return

        if self.parent.get_project() is None:
            # force a new filename...
            settings = QSettings('LANL', 'InfraView')
            previousDirectory = settings.value("last_stationfile_directory", QDir.homePath())
        else:
            # There is an open project, so make the default save location correspond to what the project wants
            previousDirectory = str(self.parent.get_project().get_stationsPath())

        self.savefile = QFileDialog.getSaveFileName(self, 'Save StationXML File...', previousDirectory)

        if self.savefile[0]:
            self.inv.write(self.savefile[0], format='stationxml', validate=True)
            path = os.path.dirname(self.savefile[0])
            settings = QSettings('LANL', 'InfraView')
            settings.setValue("last_stationfile_directory", path)

    def loadStations(self):

        if self.parent.get_project() is None:
            # force a new filename...
            settings = QSettings('LANL', 'InfraView')
            previousDirectory = settings.value("last_stationfile_directory", QDir.homePath())
        else:
            # There is an open project, so make the default save location correspond to what the project wants
            previousDirectory = str(self.parent.get_project().get_stationsPath())

        ifile = QFileDialog.getOpenFileName(self, 'Open File', previousDirectory)

        if ifile[0]:
            try:
                newinventory = read_inventory(ifile[0], format='stationxml')
            except Exception:
                IPUtils.errorPopup("\nThis doesn't seem to be a valid XML file")
                return

            print("new inventory = {}".format(newinventory))
            self.merge_new_inventory(newinventory, mode='KEEP_NEW')
    
    @pyqtSlot(Inventory, str)
    def merge_new_inventory(self, new_inv, mode):

        '''
        we don't want duplicate stations in our inventory.  So we have 4 options when merging new inventories into current:
        1. Keep current stations that have duplicates, discard new duplicates
        2. Automatically keep new duplicate stations, overwriting current
        3. Prompt the user for which new duplicates to keep
        4. Replace current inventory with new inventory

        options for mode are 'APPEND_KEEP_NEW', 'APPEND_KEEP_CURRENT', 'PROMPT', 'REPLACE'
        '''

        if self.inv is None or mode == 'REPLACE':
            self.inv = new_inv.copy()

        else:
            # This is a pain.  We need to look for duplicate station codes
            current_inv_station_codes = []
            for network in self.inv.networks:
                for sta in network.stations:
                    current_inv_station_codes.append(network.code + '.' + sta.code)

            duplicate_sta_codes = []
            for network in new_inv.networks:
                for sta in network.stations:
                    if network.code + '.' + sta.code in current_inv_station_codes:
                        duplicate_sta_codes.append(network.code + '.' + sta.code)

            if mode == 'PROMPT':
                # prompt the user to see which duplicate stations to overwrite
                if self.duplicate_sta_dialog.exec_(duplicate_sta_codes):
                    selected_codes = self.duplicate_sta_dialog.get_selected_sta_codes()
                
                    for code in selected_codes:
                        trimmed_code = code.split('.')[1]

                        self.inv = self.inv.remove(station=trimmed_code)
                        
                    not_selected = self.duplicate_sta_dialog.get_not_selected_sta_codes()
                    for code in not_selected:
                        trimmed_code = code.split('.')[1]
                        new_inv = new_inv.remove(station=trimmed_code)
                    
            elif mode == 'KEEP_NEW':
                #automatically overwrite duplicates
                for code in duplicate_sta_codes:
                    trimmed_code = code.split('.')[1]
                    self.inv = self.inv.remove(station=trimmed_code)

            elif mode == 'KEEP_CURRENT':
                for code in duplicate_sta_codes:
                    trimmed_code = code.split('.')[1]
                    new_inv = new_inv.remove(station=trimmed_code)

            self.inv += new_inv
            

        # inventories have been merged, but we might have duplicate nets, so merge them 
        self.inv = self.merge_inv_networks(self.inv)

        # ready to update the view
        self.update_station_view()

    def remove_station(self, station):
        self.inv = self.inv.remove(station=station, keep_empty=False)
        self.update_station_view()
    

    def merge_inv_networks(self, inv):
        # This function exists because the notation inv += new_inv doesn't merge networks, which causes
        # issues with inv.remove()

        merged_inventory = Inventory(
                # We'll add networks later.
                networks=[],
                # The source should be the id whoever create the file.
                source="InfraView")
        
        net_code_list = []

        for network in inv.networks:
            if network.code not in net_code_list:
                # network isnt there yet, lets add it to current
                merged_inventory.networks.append(network)
                net_code_list.append(network.code)
            else:
                # network exists, lets copy the stations from it, append them to
                # the existing network, and dump it
                stas = network.stations.copy()
                # find the network with that code
                for net in merged_inventory.networks:
                    if net.code == network.code:
                        for sta in stas:
                            net.stations.append(sta)
        
        return merged_inventory

    def get_current_center(self):
        # this method will calculate the center of the current inventory and will return a [lat,lon]

        # TODO: This is not really setup right now to handle the (very rare) case where an array straddles the
        # international date line

        lat, lon, ele, cnt = 0, 0, 0, 0

        for network in self.inv:
            for station in network:
                lat += station.latitude
                lon += station.longitude
                ele += station.elevation
                cnt += 1

        return [lat / cnt, lon / cnt, ele / cnt]
    

    def reconcileStations(self):
        
        trace_ids= []

        streams = self.parent.get_streams()
        
        if streams is None:
            return  # Nothing to reconcile

        # populate a list of all the stations in the current stream
        for trace in streams:
            if trace.id not in trace_ids:
                trace_ids.append(trace.id)

        existing_channels = []
        for network in self.inv.networks:
            for station in network.stations:
                for chan in station.channels:
                    existing_channels.append(network.code + '.' + station.code + '.' + chan.location_code + '.' + chan.code)

        
        if self.matchDialog.exec_(trace_ids, existing_channels, (self.parent.get_earliest_start_time(), self.parent.get_latest_end_time())):
            new_inventory = self.matchDialog.getInventory()
            new_inventory = self.merge_inv_networks(new_inventory)

            if new_inventory is not None:
                # since the user has already chosen to overwrite the new inventory, we set the merge mode as KEEP_NEW
                self.merge_new_inventory(new_inventory, mode='KEEP_NEW')


class IPDuplicateStationDialog(QDialog):

    def __init__(self, parent):
        super(IPDuplicateStationDialog, self).__init__(parent)

        self.duplicate_sta_codes = []
        self.__buildUI__()

    def __buildUI__(self):
        self.main_layout = QVBoxLayout()
        self.label_layout = QVBoxLayout()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.button(QDialogButtonBox.Ok).setText('Replace Selected')
        buttons.button(QDialogButtonBox.Cancel).setText('Replace None')

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        self.main_layout.addLayout(self.label_layout)
        self.main_layout.addWidget(buttons)
        self.setLayout(self.main_layout)

    def exec_(self, duplicate_stas):
        self.duplicate_sta_codes = duplicate_stas

        # first lets clear out the label layout, and redraw it
        for i in reversed(range(self.label_layout.count())): 
            self.label_layout.removeWidget(self.label_layout.itemAt(i).widget())

        self.intro_label = QLabel("The following station(s) are duplicated between \nthe current inventory and the new inventory.")
        self.label_layout.addWidget(self.intro_label)

        self.checkbox_list = []
        for dup_code in self.duplicate_sta_codes:
            self.checkbox_list.append(QCheckBox(dup_code))
            self.label_layout.addWidget(self.checkbox_list[-1])
        self.label_layout.addStretch()

        return super().exec_()
    
    def get_selected_sta_codes(self):
        selected_codes = []
        for idx, check in enumerate(self.checkbox_list):
            if check.isChecked():
                selected_codes.append(self.duplicate_sta_codes[idx].split('.')[1])
        return selected_codes
    
    def get_not_selected_sta_codes(self):
        not_selected = []
        for idx, check in enumerate(self.checkbox_list):
            if not check.isChecked():
                not_selected.append(self.duplicate_sta_codes[idx].split('.')[1])
        return not_selected


class IPArrayView(QWidget):

    def __init__(self, parent):
        super().__init__(parent)

        self.sta_spi = None
        self.chan_spi = None

        self.sta_labels = []
        self.chan_labels = []

        self.show_chans_ckbox = QCheckBox('Channels')
        self.show_chans_ckbox.setChecked(True)
        self.show_chans_ckbox.stateChanged.connect(self.update_visibilities)

        self.show_stas_ckbox = QCheckBox('Stations')
        self.show_stas_ckbox.stateChanged.connect(self.update_visibilities)

        cbox_layout = QHBoxLayout()
        cbox_layout.addWidget(self.show_chans_ckbox)
        cbox_layout.addWidget(self.show_stas_ckbox)
        cbox_layout.addStretch()

        self.station_plot = pg.PlotWidget(title='Inventory Geometry')

        self.station_plot.showAxis('right')
        self.station_plot.getAxis('right').setTicks('')
        self.station_plot.showAxis('top')
        self.station_plot.getAxis('top').setTicks('')

        self.station_plot.getAxis('bottom').setLabel('Longitude')
        self.station_plot.getAxis('left').setLabel('Latitude')

        self.station_plot.enableAutoRange()
        self.station_plot.setDefaultPadding(0.04)

        self.station_plot.setAspectLocked(True, ratio=1)

        main_layout = QVBoxLayout()
        main_layout.addLayout(cbox_layout)
        main_layout.addWidget(self.station_plot)

        self.setLayout(main_layout)


    @pyqtSlot(Inventory)
    def set_data(self, inv=None):
        self.clear()

        self.sta_spots = []          # clear array of datas
        self.chan_spots = []
        self.station_plot.clear()

        self.sta_spi = pg.ScatterPlotItem()
        self.chan_spi = pg.ScatterPlotItem()
        self.station_plot.addItem(self.sta_spi)
        self.station_plot.addItem(self.chan_spi)


        if inv is not None:
            self.inv = inv
        
        for net in self.inv.networks:
            for sta in net.stations:
                loc = (sta.longitude, sta.latitude)
                self.sta_spots.append({'pos': loc, 'symbol': '+'})
                self.create_label(loc, sta.code, type='sta')

                for chan in sta.channels:
                    c_loc = (chan.longitude, chan.latitude)
                    self.chan_spots.append({'pos': c_loc, 'symbol': 'x', 'pen': {'color': 'b'}})
                    self.create_label(c_loc, sta.code + '.' + chan.code, type='chan')

        self.sta_spi.addPoints(self.sta_spots)
        self.chan_spi.addPoints(self.chan_spots)

        self.update_visibilities()

    @pyqtSlot()
    def update_visibilities(self):
        self.sta_spi.setPointsVisible(self.show_stas_ckbox.isChecked())
        self.chan_spi.setPointsVisible(self.show_chans_ckbox.isChecked())
        for label in self.sta_labels:
            label.setVisible(self.show_stas_ckbox.isChecked())
        for label in self.chan_labels:
            label.setVisible(self.show_chans_ckbox.isChecked())

    def clear(self):
        self.station_plot.clear()
        if self.sta_spi is not None:
            self.sta_spi.clear()
        if self.chan_spi is not None:
            self.chan_spi.clear()
        for label in self.sta_labels:
            self.station_plot.removeItem(label)
        for label in self.chan_labels:
            self.station_plot.removeItem(label)

        
    def create_label(self, location, label, type):
        # type can be 'sta' or 'chan'
        text_label = pg.TextItem(label)
        text_label.setPos(location[0], location[1])
        self.station_plot.addItem(text_label, ignoreBounds=True)
        if type=='sta':
            self.sta_labels.append(text_label)
        elif type=='chan':
            self.chan_labels.append(text_label)