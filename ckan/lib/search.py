import sqlalchemy
import simplejson

import ckan.model as model
from licenses import LicenseList

LIMIT_DEFAULT = 20
DEFAULT_SEARCH_FIELDS = ['name', 'title', 'tags']

class SearchOptions:
    # about the search
    q = None
    entity = 'package'
    limit = LIMIT_DEFAULT
    offset = 0
    filter_by_openness = False
    filter_by_downloadable = False
    search_notes = False

    # about presenting the results
    order_by = 'rank'
    all_fields = False
    return_objects = False

    def __init__(self, kw_dict):
        if not kw_dict.keys():
            raise Exception('no options supplied')

        assert kw_dict.keys()
        for k,v in kw_dict.items():
            # Ensure boolean fields are boolean
            if k in ['filter_by_downloadable', 'filter_by_openness', 'search_notes', 'all_fields']:
                v = v == 1 or v
            # Ensure integer fields are integer
            if k in ['offset', 'limit']:
                v = int(v)
            # Multiple tags params are added in list
            if hasattr(self, k) and k in ['tags', 'groups']:
                existing_val = getattr(self, k)
                if type(existing_val) == type([]):
                    v = existing_val + [v]
                else:
                    v = [existing_val, v]
            setattr(self, k, v)

    def __str__(self):
        return repr(self.__dict__)

class Search:
    _tokens = [ 'name', 'title', 'notes', 'tags', 'groups', 'author', 'maintainer'] 
    _open_licenses = None

    def search(self, query_string):
        assert (isinstance(query_string, unicode))
        options = SearchOptions({'q':query_string})
        return self.run(options)

    def run(self, options):
        assert (isinstance(options, SearchOptions))
        self._options = options
        self._results = {}
        general_terms, field_specific_terms = self._parse_query_string()

        if not general_terms and \
           (self._options.entity != 'package' or not field_specific_terms):
            self._results['results'] = []
            self._results['count'] = 0
            return self._results

        if self._options.entity == 'package':
            query = self._build_package_query(general_terms, field_specific_terms)
        elif self._options.entity == 'tag':
            query = self._build_tags_query(general_terms)
        elif self._options.entity == 'group':
            query = self._build_groups_query(general_terms)
        else:
            # error
            pass

        self._run_query(query)

        self._format_results()
        
        return self._results

    def _parse_query_string(self):
        query_str = self._options.q
        
        # split query into terms
        # format: * double quotes enclose a single term. e.g. "War and Peace"
        #         * field:term or field:"longer term" means search only in that
        #           particular field for that term.
        terms = []
        if query_str:
            inside_quote = False
            buf = ''
            for ch in query_str:
                if ch == ' ' and not inside_quote:
                    if buf:
                        terms.append(buf.strip())
                    buf = ''
                elif ch == '"':
                    inside_quote = not inside_quote
                else:
                    buf += ch
            if buf:
                terms.append(buf)

        # split off field-specific terms
        field_specific_terms = {}
        general_terms = []
        for term in terms:
            
            # Look for 'token:'
            token = None
            colon_pos = term.find(':')
            if colon_pos != -1:
                token = term[:colon_pos]
                if token in self._tokens:
                    term = term[colon_pos+1:]
                    if term:
                        if not field_specific_terms.has_key(token):
                            field_specific_terms[token] = []
                        field_specific_terms[token].append(term)
                else:
                    general_terms.append(term)
            else:
                general_terms.append(term)

        # add field-specific terms that have come in via the options
        for token in self._tokens:
            if self._options.__dict__.has_key(token):
                field_specific_terms[token] = getattr(self._options, token)

        # special case - 'tags:' becomes a general term when searching
        # tag entities.
        if self._options.entity == 'tag' and field_specific_terms.has_key(u'tags'):
            general_terms.extend(field_specific_terms[u'tags'])
        
        
        return general_terms, field_specific_terms

    def _build_package_query(self, general_terms, field_specific_terms):
        make_like = lambda x,y: x.ilike('%' + y + '%')
        query = model.Package.query
        query = query.filter(model.package_search_table.c.package_id==model.Package.id)

        # Full search by general_terms (and field specific terms but not by field)
        terms_set = set()
        for term_list in field_specific_terms.values():
            if isinstance(term_list, (list, tuple)):
                for term in term_list:
                    terms_set.add(term)
            else:
                terms_set.add(term_list)
        for term in general_terms:
            terms_set.add(term)
        all_terms = ' '.join(terms_set)
        query = query.filter('package_search.search_vector '\
                                       '@@ plainto_tsquery(:terms)')
        query = query.params(terms=all_terms)
            
        # Filter by field_specific_terms
        for field, terms in field_specific_terms.items():
            if field in ('tags', 'groups'):
                if type(terms) in (type(''), type(u'')):
                    query = self._filter_by_tags_or_groups(field, query, terms.split())
                else:
                    query = self._filter_by_tags_or_groups(field, query, terms)
            else:
                for term in terms:
                    model_attr = getattr(model.Package, field)
                    query = query.filter(make_like(model_attr, term))

        # Filter for options
        if self._options.filter_by_downloadable:
            query = query.filter(model.Package.download_url!='')
        if self._options.filter_by_openness:
            if self._open_licenses is None:
                self._update_open_licenses()
            query = query.filter(model.Package.license_id.in_(self._open_licenses))
        if self._options.order_by:
            if self._options.order_by == 'rank':
                query = query.add_column(sqlalchemy.func.ts_rank_cd(sqlalchemy.text('package_search.search_vector'), sqlalchemy.func.plainto_tsquery(all_terms)))
                query = query.order_by(sqlalchemy.text('ts_rank_cd_1 DESC'))
            else:
                model_attr = getattr(model.Package, self._options.order_by)
                query = query.order_by(model_attr)

        query = query.distinct()
        query = query.filter(model.Package.state == model.State.query.filter_by(name='active').one())
        return query

    def _build_tags_query(self, general_terms):
        query = model.Tag.query
        for term in general_terms:
            query = query.filter(model.Tag.name.contains(term.lower()))
        return query

    def _build_groups_query(self, general_terms):
        query = model.Group.query
        for term in general_terms:
            query = query.filter(model.Group.name.contains(term.lower()))
        return query

    def _run_query(self, query):
        # Run the query
        self._results['count'] = query.count()

        query = query.offset(self._options.offset)
        query = query.limit(self._options.limit)

        results = []
        for result in query:
            if isinstance(result, tuple) and isinstance(result[0], model.DomainObject):
                # This is the case for order_by rank due to the add_column.
                results.append(result[0])
            else:
                results.append(result)
                
        
        self._results['results'] = results

    def _filter_by_tags_or_groups(self, field, query, value_list):
        for name in value_list:
            if field == 'tags':
                tag = model.Tag.by_name(name.strip())
                if tag:
                    tag_id = tag.id
                    # need to keep joining for each filter
                    # tag should be active hence state_id requirement
                    query = query.join('package_tags', aliased=True).filter(sqlalchemy.and_(
                        model.PackageTag.state_id==1,
                        model.PackageTag.tag_id==tag_id))
                else:
                    # unknown tag, so torpedo search
                    query = query.filter(model.PackageTag.tag_id==-1)
            elif field == 'groups':
                group = model.Group.by_name(name.strip())
                if group:
                    group_id = group.id
                    # need to keep joining for each filter
                    query = query.join('groups', aliased=True).filter(
                        model.Group.id==group_id)
                else:
                    # unknown group, so torpedo search
                    query = query.filter(model.Group.id==u'-1')
                
        return query
        
    def _update_open_licenses(self):
        self._open_licenses = []
        for license_name in LicenseList.all_formatted:
            _license = model.License.by_name(license_name)
            if _license and _license.isopen():                
                self._open_licenses.append(_license.id)

    def _format_results(self):
        if not self._options.return_objects:
            if self._options.all_fields:
                results = []
                for entity in self._results['results']:
                    result = entity.as_dict()
                    results.append(result)
                self._results['results'] = results
            else:
                self._results['results'] = [entity.name for entity in self._results['results']]
        
            
        
