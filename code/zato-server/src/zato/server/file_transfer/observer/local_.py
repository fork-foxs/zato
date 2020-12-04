# -*- coding: utf-8 -*-

"""
Copyright (C) Zato Source s.r.o. https://zato.io

Licensed under LGPLv3, see LICENSE.txt for terms and conditions.
"""

from __future__ import absolute_import, division, print_function, unicode_literals

# stdlib
from traceback import format_exc

# stdlib
import os
from logging import getLogger

# Watchdog
from watchdog.utils.dirsnapshot import DirectorySnapshot

# Zato
from zato.common.util.api import spawn_greenlet
from zato.common.util.platform_ import is_linux
from .base import BaseObserver

# ################################################################################################################################
# ################################################################################################################################

logger = getLogger(__name__)

# ################################################################################################################################
# ################################################################################################################################

class PathCreatedEvent:
    __slots__ = 'src_path'

    def __init__(self, src_path):
        self.src_path = src_path

# ################################################################################################################################
# ################################################################################################################################

class LocalObserver(BaseObserver):
    """ A local file-system observer.
    """
    observer_type_name = 'local file'
    observer_type_name_title = observer_type_name.upper()
    should_wait_for_deleted_paths = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if is_linux:
            self.observer_type_impl = 'local-inotify'
            self._observe_func = self.observe_with_inotify
        else:
            self.observer_type_impl = 'local-snapshot'
            self._observe_func = self.observe_with_snapshots

# ################################################################################################################################

    def get_dir_snapshot(path, is_recursive):
        """ Returns a directory snapshot (unused under Linux with inotify).
        """
        return DirectorySnapshot(path, recursive=is_recursive)

# ################################################################################################################################

    def path_exists(self, path, _ignored_snapshot_maker=None):
        return os.path.exists(path)

# ################################################################################################################################

    def path_is_directory(self, path, _ignored_snapshot_maker=None):
        return os.path.isdir(path)

# ################################################################################################################################

    def delete_file(self, path, _ignored_snapshot_maker):
        """ Deletes a file pointed to by path.
        """
        os.remove(full_path)

# ################################################################################################################################

    def observe_with_inotify(self, path, observer_start_args):
        """ Local observer's main loop for Linux, uses inotify.
        """
        # type: (str, tuple) -> None
        try:

            inotify, inotify_flags, lock_func, wd_to_path_map = observer_start_args

            # Create a new watch descriptor
            wd = inotify.add_watch(path, inotify_flags)

            # .. and map the input path to wd for use in higher-level layers.
            with lock_func:
                wd_to_path_map[wd] = path

        except Exception:
            logger.warn("Exception in inotify observer's main loop `%s`", format_exc())

# ################################################################################################################################

    def is_path_valid(self, path):
        # type: (str) -> bool
        return self.path_exists(path) and self.path_is_directory(path)

# ################################################################################################################################
# ################################################################################################################################
