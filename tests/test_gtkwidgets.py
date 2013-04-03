#!/usr/bin/python3
# -*- coding: utf-8; -*-

import sys
from test.support import run_unittest
import unittest

import dbus
from gi.repository import Gtk, TimezoneMap
import mock

from ubiquity import gtkwidgets, nm, segmented_bar


class MockController(object):
    def get_string(self, name, lang=None, prefix=None):
        return "%s: %s" % (lang, name)


class WidgetTests(unittest.TestCase):
    def setUp(self):
        self.err = None

        def excepthook(exctype, value, tb):
            # Workaround for http://bugzilla.gnome.org/show_bug.cgi?id=616279
            Gtk.main_quit()
            self.err = exctype, value, tb

        sys.excepthook = excepthook
        self.win = Gtk.Window()

    def tearDown(self):
        self.win.hide()
        if self.err:
            exctype, value, tb = self.err
            if value.__traceback__ is not tb:
                raise value.with_traceback(tb)
            else:
                raise value

    def test_segmented_bar(self):
        sb = segmented_bar.SegmentedBar()
        self.win.add(sb)
        sb.add_segment_rgb('Test One', 30 * 1000 * 1000 * 1000, 'ff00ff')
        sb.add_segment_rgb('Test Two', 30 * 1000 * 1000 * 1000, '0000ff')
        for segment in sb.segments:
            self.assertEqual(segment.subtitle, '30.0 GB')
        self.assertEqual(sb.segments[0].title, 'Test One')
        self.assertEqual(sb.segments[1].title, 'Test Two')
        sb.remove_all()
        self.assertEqual(sb.segments, [])
        self.win.show_all()
        gtkwidgets.refresh()

    def test_timezone_map(self):
        tzmap = TimezoneMap.TimezoneMap()
        self.win.add(tzmap)
        #tzmap.select_city('America/New_York')
        self.win.show_all()
        self.win.connect('destroy', Gtk.main_quit)
        gtkwidgets.refresh()

    def test_state_box(self):
        sb = gtkwidgets.StateBox('foobar')
        self.assertEqual(sb.get_property('label'), 'foobar')
        sb.set_property('label', 'barfoo')
        self.assertEqual(sb.get_property('label'), 'barfoo')
        sb.set_state(True)
        self.assertEqual(sb.image.get_stock(),
                         ('gtk-yes', Gtk.IconSize.LARGE_TOOLBAR))
        self.assertEqual(sb.get_state(), True)
        sb.set_state(False)
        self.assertEqual(sb.image.get_stock(),
                         ('gtk-no', Gtk.IconSize.LARGE_TOOLBAR))
        self.assertEqual(sb.get_state(), False)

    def test_gtk_to_cairo_color(self):
        self.assertEqual(gtkwidgets.gtk_to_cairo_color('white'),
                         (1.0, 1.0, 1.0))
        self.assertEqual(gtkwidgets.gtk_to_cairo_color('black'), (0, 0, 0))
        # After all these years a discrepancy between X11 green and CSS
        # green was noticed
        self.assertEqual(gtkwidgets.gtk_to_cairo_color('#00ff00'), (0, 1.0, 0))
        self.assertEqual(gtkwidgets.gtk_to_cairo_color('red'), (1.0, 0, 0))
        self.assertEqual(gtkwidgets.gtk_to_cairo_color('blue'), (0, 0, 1.0))

udevinfo = """
UDEV_LOG=3
DEVPATH=/devices/pci0000:00/0000:00:1c.1/0000:03:00.0/net/wlan0
DEVTYPE=wlan
INTERFACE=wlan0
IFINDEX=3
SUBSYSTEM=net
ID_VENDOR_FROM_DATABASE=Intel Corporation
ID_MODEL_FROM_DATABASE=PRO/Wireless 3945ABG [Golan] Network Connection
ID_BUS=pci
ID_VENDOR_ID=0x8086
ID_MODEL_ID=0x4227
ID_MM_CANDIDATE=1
"""


class NetworkManagerTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch('ubiquity.nm.NetworkManager.start')
        patcher.start()
        self.addCleanup(patcher.stop)
        self.model = Gtk.TreeStore(str, object, object)
        self.manager = nm.NetworkManager(self.model)

    @mock.patch('subprocess.Popen')
    def test_get_vendor_and_model_null(self, mock_subprocess):
        mock_subprocess.return_value.communicate.return_value = (
            '', 'device path not found\n')
        self.assertEqual(nm.get_vendor_and_model('bogus'), ('', ''))

    @mock.patch('subprocess.Popen')
    def test_get_vendor_and_model(self, mock_subprocess):
        mock_subprocess.return_value.communicate.return_value = (
            udevinfo, None)
        self.assertEqual(nm.get_vendor_and_model('foobar'),
                         ('Intel Corporation',
                          'PRO/Wireless 3945ABG [Golan] Network Connection'))

    def test_decode_ssid(self):
        ssid = [dbus.Byte(85), dbus.Byte(98), dbus.Byte(117), dbus.Byte(110),
                dbus.Byte(116), dbus.Byte(117), dbus.Byte(45), dbus.Byte(66),
                dbus.Byte(97), dbus.Byte(116), dbus.Byte(116), dbus.Byte(101),
                dbus.Byte(114), dbus.Byte(115), dbus.Byte(101), dbus.Byte(97)]
        self.assertEqual(nm.decode_ssid(ssid), 'Ubuntu-Battersea')

    def test_decode_ssid_utf8(self):
        ssid = [dbus.Byte(82), dbus.Byte(195), dbus.Byte(169), dbus.Byte(115),
                dbus.Byte(101), dbus.Byte(97), dbus.Byte(117)]
        self.assertEqual(nm.decode_ssid(ssid), 'Réseau')

    def test_decode_ssid_latin1(self):
        ssid = [dbus.Byte(82), dbus.Byte(233), dbus.Byte(115), dbus.Byte(101),
                dbus.Byte(97), dbus.Byte(117)]
        self.assertEqual(nm.decode_ssid(ssid), 'R\ufffdseau')

    def test_ssid_in_model(self):
        iterator = self.model.append(None, ['/foo', 'Intel', 'Wireless'])
        for ssid in ('Orange', 'Apple', 'Grape'):
            self.model.append(iterator, [ssid, True, 0])
        self.assertIsNotNone(
            self.manager.ssid_in_model(iterator, 'Apple', True))
        self.assertIsNone(self.manager.ssid_in_model(iterator, 'Grape', False))

    def test_prune(self):
        iterator = self.model.append(None, ['/foo', 'Intel', 'Wireless'])
        fruits = ['Orange', 'Apple', 'Grape']
        for ssid in fruits:
            self.model.append(iterator, [ssid, True, 0])
        i = self.model.iter_children(iterator)
        self.manager.prune(i, fruits)
        ret = []
        while i:
            ret.append(self.model[i][0])
            i = self.model.iter_next(i)
        # There haven't been any changes in this update.
        self.assertListEqual(fruits, ret)
        # An AP that was present no longer is.
        fruits.pop()
        i = self.model.iter_children(iterator)
        self.manager.prune(i, fruits)
        ret = []
        while i:
            ret.append(self.model[i][0])
            i = self.model.iter_next(i)
        self.assertListEqual(fruits, ret)

    def test_pixbuf_func(self):
        iterator = self.model.append(None, ['/foo', 'Intel', 'Wireless'])
        mock_cell = mock.Mock()
        tv = nm.NetworkManagerTreeView()
        tv.pixbuf_func(None, mock_cell, self.model, iterator, None)
        mock_cell.set_property.assert_called_with('pixbuf', None)
        # 0% strength, protected network
        i = self.model.append(iterator, ['Orange', True, 0])
        tv.pixbuf_func(None, mock_cell, self.model, i, None)
        mock_cell.set_property.assert_called_with('pixbuf', tv.icons[5])
        # 30% strength, protected network
        self.model.set_value(i, 2, 30)
        tv.pixbuf_func(None, mock_cell, self.model, i, None)
        mock_cell.set_property.assert_called_with('pixbuf', tv.icons[6])
        # 95% strength, unprotected network
        self.model.set_value(i, 1, False)
        self.model.set_value(i, 2, 95)
        tv.pixbuf_func(None, mock_cell, self.model, i, None)
        mock_cell.set_property.assert_called_with('pixbuf', tv.icons[4])

    def test_data_func(self):
        iterator = self.model.append(None, ['/foo', 'Intel', 'Wireless'])
        mock_cell = mock.Mock()
        tv = nm.NetworkManagerTreeView()
        tv.data_func(None, mock_cell, self.model, iterator, None)
        mock_cell.set_property.assert_called_with('text', 'Intel Wireless')
        i = self.model.append(iterator, ['Orange', True, 0])
        tv.data_func(None, mock_cell, self.model, i, None)
        mock_cell.set_property.assert_called_with('text', 'Orange')

if __name__ == '__main__':
    run_unittest(WidgetTests, NetworkManagerTests)
