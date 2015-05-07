%if 0%{?rhel} && 0%{?rhel} <= 6
%global have_rhel6 1
%global want_systemd 0
%else
%global have_rhel6 0
%global want_systemd 1
%endif

%global sahara_user sahara
%global sahara_group %{sahara_user}

%if %{have_rhel6}
%{!?__python2: %global __python2 /usr/bin/python2}
%{!?python2_sitelib: %global python2_sitelib %(%{__python2} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python2_sitearch: %global python2_sitearch %(%{__python2} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}
%endif

%if 0%{?rhel} && 0%{?rhel} <= 7
%{!?_pkgdocdir: %global _pkgdocdir %{_docdir}/%{name}}
%endif

Name:          openstack-sahara
Version:       2014.1.1
Release:       1%{?dist}
Provides:      openstack-savanna = %{version}-%{release}
Summary:       Apache Hadoop cluster management on OpenStack
License:       ASL 2.0
URL:           https://launchpad.net/sahara
Source0:       http://tarballs.openstack.org/sahara/sahara-%{version}.tar.gz
Source1:       openstack-sahara-api.service
Source2:       openstack-sahara-api.init
BuildArch:     noarch

#
# patches_base=2014.1.1
#
Patch0001: 0001-remove-runtime-dep-on-python-pbr.patch
Patch0002: 0002-reference-actual-plugins-shipped-in-tarball.patch

BuildRequires: python2-devel
BuildRequires: python-setuptools
BuildRequires: python-sphinx >= 1.1.2
BuildRequires: python-oslo-sphinx
BuildRequires: python-sphinxcontrib-httpdomain
BuildRequires: python-pbr >= 0.5.19

%if %{want_systemd}
# Need systemd-units for _unitdir macro
BuildRequires: systemd-units
%endif

Requires: python-alembic
#?Babel>=1.3?
Requires: python-eventlet
Requires: python-flask
Requires: python-iso8601
Requires: python-jsonschema >= 1.3.0
Requires: python-oslo-config >= 1.2.0
Requires: python-oslo-messaging
Requires: python-paramiko >= 1.9.0
Requires: python-cinderclient >= 1.0.5
Requires: python-keystoneclient >= 0.6.0
Requires: python-novaclient >= 2.15.0
Requires: python-swiftclient
Requires: python-neutronclient
Requires: python-six >= 1.4.1
Requires: python-stevedore >= 0.14
Requires: python-webob
Requires: python-sqlalchemy

%if %{want_systemd}
Requires(post):   systemd
Requires(preun):  systemd
Requires(postun): systemd
%else
Requires(post):   chkconfig
Requires(preun):  initscripts
Requires(postun): chkconfig
%endif
Requires(pre):    shadow-utils


%package doc
Group:         Documentation
Summary:       Usage documentation for the Sahara cluster management API
Requires:      %{name} = %{version}


%description
Sahara provides the ability to elastically manage Apache Hadoop clusters on
OpenStack.


%description doc
Sahara provides the ability to elastically manage Apache Hadoop clusters on
OpenStack. This documentation provides instructions and examples on how to
install, use, and manage the Sahara infrastructure.


%prep
%setup -q -n sahara-%{version}

%patch0001 -p1
%patch0002 -p1

sed -i s/REDHAT_SAHARA_VERSION/%{version}/ sahara/version.py
sed -i s/REDHAT_SAHARA_RELEASE/%{release}/ sahara/version.py

rm -rf sahara.egg-info
rm -f test-requirements.txt
# The data_files glob appears broken in pbr 0.5.19, so be explicit
sed -i 's,etc/sahara/\*,etc/sahara/sahara.conf.sample,' setup.cfg
# remove the shbang from these files to supress rpmlint warnings, these are
# python based scripts that get processed to form the installed shell scripts.
sed -i 1,2d sahara/cli/sahara_api.py
sed -i 1,2d sahara/cli/sahara_subprocess.py
# set executable on this file to supress rpmlint warnings, it is used as a
# template to create shell scripts.
chmod a+x sahara/plugins/vanilla/v2_3_0/resources/post_conf.template


%build
%{__python2} setup.py build

export PYTHONPATH=$PWD:${PYTHONPATH}
# Note: json warnings likely resolved w/ pygments 1.5 (not yet in Fedora)
# make doc build compatible with python-oslo-sphinx RPM
sed -i 's/oslosphinx/oslo.sphinx/' doc/source/conf.py
sphinx-build doc/source html
rm -rf html/.{doctrees,buildinfo}


%install
%{__python2} setup.py install --skip-build --root %{buildroot}

%if %{want_systemd}
install -p -D -m 644 %{SOURCE1} %{buildroot}%{_unitdir}/openstack-sahara-api.service
%else
install -d -m 755 %{buildroot}%{_localstatedir}/run/sahara
install -p -D -m 755 %{SOURCE2} %{buildroot}%{_initrddir}/openstack-sahara-api
%endif

HOME=%{_sharedstatedir}/sahara
install -d -m 700 %{buildroot}$HOME

# TODO: os_admin_username/password/tenant_name
SAMPLE=%{buildroot}%{_datadir}/sahara/sahara.conf.sample
CONF=%{buildroot}%{_sysconfdir}/sahara/sahara.conf
install -d -m 755 $(dirname $CONF)
install -D -m 640 $SAMPLE $CONF
sed -i -e "s,.*connection=.*,connection=sqlite:///$HOME/sahara-server.db," $CONF

# Do not package tests
rm -rf %{buildroot}%{python_sitelib}/sahara/tests

mkdir -p -m0755 %{buildroot}/%{_localstatedir}/log/sahara

# Copy built doc files for doc subpackage
mkdir -p %{buildroot}/%{_pkgdocdir}
cp -rp html %{buildroot}/%{_pkgdocdir}


%check
# Building on koji with virtualenv requires test-requirements.txt and this
# causes errors when trying to resolve the package names, also turning on pep8
# results in odd exceptions from flake8.
# TODO mimccune fix up unittests
# sh run_tests.sh --no-virtual-env --no-pep8


%pre
# Origin: http://fedoraproject.org/wiki/Packaging:UsersAndGroups#Dynamic_allocation
USERNAME=%{sahara_user}
GROUPNAME=%{sahara_group}
HOMEDIR=%{_sharedstatedir}/sahara
getent group $GROUPNAME >/dev/null || groupadd -r $GROUPNAME
getent passwd $USERNAME >/dev/null || \
  useradd -r -g $GROUPNAME -G $GROUPNAME -d $HOMEDIR -s /sbin/nologin \
  -c "Sahara Daemons" $USERNAME
exit 0


%post
# TODO: if db file then sahara-db-manage update head
%if %{want_systemd}
%systemd_post openstack-sahara-api.service
%else
/sbin/chkconfig --add openstack-sahara-api
%endif


%preun
%if %{want_systemd}
%systemd_preun openstack-sahara-api.service
%else
if [ $1 -eq 0 ] ; then
   /sbin/service openstack-sahara-api stop >/dev/null 2>&1
   /sbin/chkconfig --del openstack-sahara-api
fi
%endif


%postun
%if %{want_systemd}
%systemd_postun_with_restart openstack-sahara-api.service
%else
if [ $1 -ge 1 ] ; then
   # Package upgrade, not uninstall
   /sbin/service openstack-sahara-api condrestart > /dev/null 2>&1 || :
fi
%endif


%files
%doc README.rst LICENSE

%if %{have_rhel6}
%dir %attr(0755, %{sahara_user}, root) %{_localstatedir}/run/sahara
%{_initrddir}/openstack-sahara-api
%else
%{_unitdir}/openstack-sahara-api.service
%endif

%dir %{_sysconfdir}/sahara
# Note: this file is not readable because it holds auth credentials
%config(noreplace) %attr(-, root, %{sahara_group}) %{_sysconfdir}/sahara/sahara.conf
%{_bindir}/sahara-api
%{_bindir}/_sahara-subprocess
%{_bindir}/sahara-db-manage
%dir %attr(-, %{sahara_user}, %{sahara_group}) %{_sharedstatedir}/sahara
%dir %attr(-, %{sahara_user}, %{sahara_group}) %{_localstatedir}/log/sahara
# Note: permissions on sahara's home are intentially 0700
%dir %{_datadir}/sahara
%{_datadir}/sahara/sahara.conf.sample
%{python_sitelib}/sahara
%{python_sitelib}/sahara-%{version}-py?.?.egg-info


%files doc
%{_pkgdocdir}/html 


%changelog
* Thu Jul 17 2014 Pádraig Brady <pbrady@redhat.com> - 2014.1.1-1
- Stable icehouse 2014.1.1 rebase

* Sat Jun 07 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2014.1.0-14
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Wed May 07 2014 Michael McCune <mimccune@redhat> - 2014.1.0-13
- Adding missing shell scripts to manifest patch

* Mon May 05 2014 Michael McCune <mimccune@redhat> - 2014.1.0-12
- Patching MANIFEST.in for missing hdp plugin resources and alembic migrations
- Removing the cp for alembic migrations

* Mon May 05 2014 Michael McCune <mimccune@redhat> - 2014.1.0-11
- Adding BuildRequire for python-sphinx

* Mon May 05 2014 Michael McCune <mimccune@redhat> - 2014.1.0-10
- Removing pbr from Requires
- changing version and release temp from patch

* Mon May 05 2014 Michael McCune <mimccune@redhat> - 2014.1.0-9
- Adding patch to remove runtime pbr requirement

* Fri May 02 2014 Michael McCune <mimccune@redhat> - 2014.1.0-8
- Removing python-sqlalchemy and python-paste-deploy from BuildRequires
- refactoring the systemd portions

* Fri May 02 2014 Michael McCune <mimccune@redhat> - 2014.1.0-7
- Changing parallel build require for python-sqlalchemy0.7
- Removing chmod in post
- Replacing user/group in attrs with global variables

* Wed Apr 30 2014 Michael McCune <mimccune@redhat> - 2014.1.0-6
- Adding sahara user ownership to log dir
- Creating local variables for sahara user and group

* Wed Apr 30 2014 Michael McCune <mimccune@redhat> - 2014.1.0-5
- Adding alembic migration files, addressing BZ1094757

* Wed Apr 30 2014 Michael McCune <mimccune@redhat> - 2014.1.0-4
- Correcting bug with rhel6 init script, addressing BZ1094755
- Adding local variable for rhel6 tests

* Thu Apr 24 2014 Michael McCune <mimccune@redhat> - 2014.1.0-3
- merging in el6 spec, with conditionals

* Thu Apr 24 2014 Michael McCune <mimccune@redhat> - 2014.1.0-2
- adding _pkgdocdir macro for rhel<=7

* Tue Apr 22 2014 Michael McCune <mimccune@redhat> - 2014.1.0-1
- 2014.1 release

* Tue Apr 08 2014 Michael McCune <mimccune@redhat> - 2014.1.rc1-1
- 2014.1.rc1 release and rename from openstack-savanna

* Fri Mar 14 2014 Matthew Farrellee <matt@redhat> - 2014.1.b3-2
- Fixed python-webob dependency version

* Mon Mar 10 2014 Matthew Farrellee <matt@redhat> - 2014.1.b3-1
- 2014.1.b3 release

* Mon Jan 27 2014 Matthew Farrellee <matt@redhat> - 2014.1.b2-3
- Require stevedore >= 0.13

* Mon Jan 27 2014 Matthew Farrellee <matt@redhat> - 2014.1.b2-2
- Added space around paramiko requires

* Mon Jan 27 2014 Matthew Farrellee <matt@redhat> - 2014.1.b2-1
- 2014.1.b2 release

* Sat Jan 18 2014 Matthew Farrellee <matt@redhat> - 2014.1.b1-1
- 2014.1.b1 release

* Tue Oct 22 2013 Matthew Farrellee <matt@redhat> - 0.3-3
- Include Vanilla Plugin SQL files (for EDP)

* Tue Oct 22 2013 Matthew Farrellee <matt@redhat> - 0.3-2
- Fix db connection url

* Sun Oct 20 2013 Matthew Farrellee <matt@redhat> - 0.3-1
- 0.3 release
- Enable logging into /var/log/savanna

* Fri Oct 11 2013 Matthew Farrellee <matt@redhat> - 0.3-0.2
- 0.3 rc3 build

* Mon Aug 12 2013 Matthew Farrellee <matt@redhat> - 0.2-3
- Updates to build on F19,
-  Require systemd-units, allows mockbuild to work
-  Remove setuptools-git from setup.py, no downloads during build

* Fri Aug 09 2013 Matthew Farrellee <matt@redhat> - 0.2-2
- Updates from package review BZ986615

* Mon Jul 15 2013 Matthew Farrellee <matt@redhat> - 0.2-1
- Initial package
