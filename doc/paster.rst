=================
Common CKAN Tasks
=================

The majority of common CKAN administration tasks are carried out using the **paster** script. 

Paster is run on the command line on the server running CKAN. This section covers:

* :ref:`paster-understanding`. Understanding paster syntax and getting help. 
* :ref:`paster-tasks`. How to carry out common CKAN admin tasks using paster.

.. _paster-understanding:

Understanding Paster
====================

The basic paster format is:: 

  paster --plugin=ckan <ckan commands> --config=<config file>

For example, to initialise a database::

  paster --plugin=ckan db init --config=/etc/ckan/std/std.ini


.. _paster-help:

Getting Help on Paster
----------------------

To get a full list of paster commands (i.e. including CKAN commands)::

  paster --plugin=ckan --help

And to get more detailed help on each command (e.g. on ``db``)::

  paster --plugin=ckan --help db


Position of Paster Parameters
-----------------------------

The position of paster parameters matters. 

``--plugin`` is a parameter to paster, so needs to come before the CKAN command. To do this, the first parameter to paster is normally ``--plugin=ckan``.

.. note:: The default value for ``--plugin`` is ``setup.py`` in the current directory. If you are running paster from the directory where CKAN's ``setup.py`` file is located, you don't need to specify the plugin parameter.. 

Meanwhile, ``--config`` is a parameter to CKAN, so needs to come after the CKAN command. This specifies the CKAN config file for the instance you want to use, e.g. ``--config=/etc/ckan/std/std.ini``

.. note:: The default value for ``--config`` is ``development.ini`` in the current directory. If you are running a package install of CKAN (as described in :doc:`install-from-package`), you should explicitly specify ``std.ini``.

The position of the CKAN command itself is less important, as longs as it follows ``--plugin``. For example, both the following commands have the same effect:::

  paster --plugin=ckan db --config=development.ini init
  paster --plugin=ckan db init --config=development.ini


Running a Paster Shell
----------------------

If you want to run a "paster shell", which can be useful for development, then the plugin is pylons. e.g. ``paster --plugin=pylons shell``. 

Often you will want to run this as the same user as the web application, to ensure log files are written as the same user. And you'll also want to specify a config file (note that this is not specified using the ``--config`` parameter, but simply as the final argument). For example::

  sudo -u www-data paster --plugin=pylons shell std.ini


.. _paster-tasks:

Common Tasks Using Paster
=========================

The following tasks are supported by paster.

  ================= ==========================================================
  create-test-data  Create test data in the database.
  db                Perform various tasks on the database.
  ratings           Manage the ratings stored in the db
  rights            Commands relating to per-object and system-wide access rights.
  roles             Commands relating to roles and actions.
  search-index      Creates a search index for all packages
  sysadmin          Gives sysadmin rights to a named user
  user              Manage users
  ================= ==========================================================


For the full list of tasks supported by paster, you can run::
  
 paster --plugin=ckan --help


create-test-data: Create test data
----------------------------------

As the name suggests, this command lets you load test data when first setting up CKAN. See :ref:`create-test-data` for details. 


db: Manage databases
--------------------

Lets you initialise, upgrade, and dump the CKAN database. 

Initialisation
~~~~~~~~~~~~~~

Before you can run CKAN for the first time, you need to run "db init" to create the tables in the database and the default authorization settings::

 paster --plugin=ckan db init --config=/etc/ckan/std/std.ini

If you forget to do this then CKAN won't serve requests and you will see errors such as this in the logs::

 ProgrammingError: (ProgrammingError) relation "user" does not exist

Cleaning
~~~~~~~~

You can delete everything in the CKAN database, including the tables, to start from scratch::

 paster --plugin=ckan db clean --config=/etc/ckan/std/std.ini

The next logical step from this point is to do a "db init" step before starting CKAN again.

Upgrade migration
~~~~~~~~~~~~~~~~~

When you upgrade CKAN software by any method *other* than the package update described in :doc:`upgrade`, before you restart it, you should run 'db upgrade', which will do any necessary migrations to the database tables::

 paster --plugin=ckan db upgrade --config=/etc/ckan/std/std.ini

Creating dump files
~~~~~~~~~~~~~~~~~~~

For information on using ``db`` to create dumpfiles, see :doc:`database_dumps`.


ratings: Manage package ratings
-------------------------------

Manages the ratings stored in the database, and can be used to count ratings, remove all ratings, or remove only anonymous ratings. 

For example, to remove anonymous ratings from the database::

 paster --plugin=ckan ratings clean-anonymous --config=/etc/ckan/std/std.ini


rights: Set user permissions
----------------------------

Sets the authorization roles of a specific user on a given object within the system.

For example, to give the user named 'bar' the 'admin' role on the package 'foo'::

 paster --plugin=ckan rights make bar admin package:foo  --config=/etc/ckan/std/std.ini

To list all the rights currently specified::

 paster --plugin=ckan rights list --config=/etc/ckan/std/std.ini 

For more information and examples, see :doc:`authorization`.


roles: Manage system-wide permissions
--------------------------------------

This important command gives you fine-grained control over CKAN permissions, by listing and modifying the assignment of actions to roles. 

The ``roles`` command has its own section: see :doc:`authorization`.


search-index: Rebuild search index
----------------------------------

Rebuilds the search index defined in the :ref:`config-search-backend` config setting. This is useful to prevent search indexes from getting out of sync with the main database.

For example::

 paster --plugin=ckan search-index --config=/etc/ckan/std/std.ini


sysadmin: Give sysadmin rights
------------------------------

Gives sysadmin rights to a named user. This means the user can perform any action on any object. 

For example, to make a user called 'admin' into a sysadmin::

 paster --plugin=ckan sysadmin add admin --config=/etc/ckan/std/std.ini


.. _paster-user:

user: Create and manage users
-----------------------------

Lets you create, remove, list and manage users.

For example, to create a new user called 'admin'::

 paster --plugin=ckan user add admin --config=/etc/ckan/std/std.ini

To delete the 'admin' user::

 paster --plugin=ckan user delete admin --config=/etc/ckan/std/std.ini
