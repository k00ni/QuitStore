from flask import Response
from rdflib import ConjunctiveGraph, Graph, URIRef
from GitRepo import GitRepo
from QueryCheck import QueryCheck
import os


class MemoryStore:
    """A class that combines and syncronieses n-quad files and an in-memory quad store.

    This class contains information about all graphs, their corresponding URIs and
    pathes in the file system. For every Graph (context of Quad-Store) exists a
    FileReference object (n-quad) that enables versioning (with git) and persistence.
    """

    path = None

    def __init__(self):
        """Initialize a new MemoryStore instance."""
        self.sysconf = Graph()
        self.sysconf.parse('config.ttl', format='turtle')
        self.store = ConjunctiveGraph(identifier='default')
        self.path = self.getstorepath()
        self.repo = GitRepo(self.path)
        self.files = {}
        return

    def __reinit(self):
        """Renitialize the ConjunctiveGraph."""
        self.store = ConjunctiveGraph(identifier='default')

        for graphuri in self.getgraphuris():
            filereference = self.getgraphobject(graphuri)
            graph = filereference.getgraphfromfile()

            try:
                self.store.addN((None, None, None, None))
            except:
                print('Something went wrong with file for graph: ', graphuri)
                self.store.__removefile(graphuri)
                pass

            graph = None

        return

    def __updatecontentandsave(self):
        """Update the files after a update query was executed on the store and save."""
        for graphuri, fileobject in self.getgraphs():
            content = self.getgraphcontent(graphuri)
            fileobject.setcontent(content)
            fileobject.savefile()

        return

    def __savefiles(self):
        """Update the files after a update query was executed on the store."""
        for graphuri, fileobject in self.getgraphs():
            if fileobject.isversioned():
                fileobject.savefile()

        return

    def __updategit(self):
        """Private method to add all updated tracked files."""
        self.repo.update()

        return

    def __removefile(self, graphuri):
        try:
            del self.files[graphuri]
        except:
            return

        try:
            self.store.remove((None, None, None, graphuri))
        except:
            return

        return

    def __commit(self, message=None):
        """Private method to commit the changes."""
        try:
            self.repo.commit(message)
        except:
            pass

        return

    def getgraphs(self):
        """Method to get all available (public) named graphs.

        Returns:
            A dictionary of graphuri:FileReference tuples.
        """
        return self.files.items()

    def storeisvalid(self):
        """Check if the given MemoryStore is valid.

        Returns:
            True if, Fals if not.
        """
        graphsfromconf = list(self.getgraphsfromconf().values())
        graphsfromdir = self.getgraphsfromdir()

        for filename in graphsfromconf:
            if filename not in graphsfromdir:
                return False
            else:
                print('File found')
        return True

    def getgraphuris(self):
        """Return all URIs of named graphs.

        Returns:
            A dictionary containing all URIs of named graphs.
        """
        return self.files.keys()

    def getgraphobject(self, graphuri):
        """Return the FileReference object for a named graph URI.

        Args:
            graphuri: A string containing the URI of a named graph

        Returns:
            The FileReference object if graphuri is a named graph of MemoryStore.
            None if graphuri is not a named graph of MemoryStore.
        """
        for k, v in self.files.items():
            if k == graphuri:
                return v
        return

    def graphexists(self, graphuri):
        """Ask if a named graph FileReference object for a named graph URI.

        Args:
            graphuri: A string containing the URI of a named graph

        Returns:
            The FileReference object if graphuri is a named graph of MemoryStore.
            None if graphuri is not a named graph of MemoryStore.
        """
        graphuris = list(self.files.keys())
        try:
            graphuris.index(graphuri)
            return True
        except ValueError:
            return False

    def addFile(self, graphuri, FileReferenceObject):
        """Add a file to the store.

        This method looks if file is already part of repo.
        If not, test if given path exists, is file, is valid.
        If so, import into grahp and edit triple to right path if needed.

        Args:
            graphuri: The URI of a named graph.
            FileReferenceObject: The FileReference instance linking the quad file.
        Raises:
            ValueError if the given file can't be parsed as nquads.
        """
        self.files[graphuri] = FileReferenceObject
        try:
            newgraph = FileReferenceObject.getgraphfromfile()
            self.store.addN(newgraph.quads((None, None, None, None)))
            newgraph = None
        except:
            print('Something went wrong with file')
            raise ValueError

        return

    def getconfforgraph(self, graphuri):
        """Get the configuration for a named graph.

        This method returns configuration parameters (e.g. path to file) for a named graph.

        Args:
            graphuri: The URI if a named graph.
        Returns:
            A dictionary of configuration parameters and their values.
        """
        nsQuit = 'http://quit.aksw.org'
        query = 'SELECT ?graphuri ?filename WHERE { '
        query+= '  <' + graphuri + '> <' + nsQuit + '/Graph> . '
        query+= '  ?graph <' + nsQuit + '/graphUri> ?graphuri . '
        query+= '  ?graph <' + nsQuit + '/hasQuadFile> ?filename . '
        query+= '}'
        result = self.sysconf.query(query)

        values = {}

        for row in result:
            values[str(row['graphuri'])] = str(row['filename'])

        return values

    def getgraphsfromconf(self):
        """Get all URIs of graphs that are configured in config.ttl.

        This method returns all graphs and their corroesponding quad files.

        Returns:
            A dictionary of URIs of named graphs their quad files.
        """
        nsQuit = 'http://quit.aksw.org'
        query = 'SELECT DISTINCT ?graphuri ?filename WHERE { '
        query+= '  ?graph a <' + nsQuit + '/Graph> . '
        query+= '  ?graph <' + nsQuit + '/graphUri> ?graphuri . '
        query+= '  ?graph <' + nsQuit + '/hasQuadFile> ?filename . '
        query+= '}'
        result = self.sysconf.query(query)
        values = {}

        for row in result:
            values[str(row['graphuri'])] = str(row['filename'])

        return values

    def getgraphsfromdir(self):
        """Get the files that are part of the repository (tracked or not).

        Returns:
            A list of filepathes.
        """
        path = self.path
        files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]

        return files

    def getstoresettings(self):
        """Get the path of Git repository from configuration.

        Returns:
            A list of all repositories given in configuration.
        """
        nsQuit = 'http://quit.aksw.org'
        query = 'SELECT ?gitrepo WHERE { '
        query+= '  <http://my.quit.conf/store> <' + nsQuit + '/pathOfGitRepo> ?gitrepo . '
        query+= '}'
        result = self.sysconf.query(query)
        settings = {}
        for value in result:
            settings['gitrepo'] = value['gitrepo']

        return settings

    def getstorepath(self):
        """Return the path of the repository.

        Returns:
            A string containing the path of git repository.
        """
        if self.path is None:
            nsQuit = 'http://quit.aksw.org'
            query = 'SELECT ?gitrepo WHERE { '
            query+= '  <http://my.quit.conf/store> <' + nsQuit + '/pathOfGitRepo> ?gitrepo . '
            query+= '}'
            result = self.sysconf.query(query)
            for value in result:
                self.directory = value['gitrepo']

        return self.directory

    def processsparql(self, querystring):
        """Execute a sparql query after analyzing the query string.

        Args:
            querystring: A SPARQL query string.
        Returns:
            SPARQL result set if valid select query.
            None if valid update query.
        Raises:
            Exception: If query is not a valid SPARQL update or select query

        """
        query = QueryCheck(querystring)
        '''
        try:
            query = QueryCheck(querystring)
        except:
            raise
        '''

        if query.getType() == 'SELECT':
            print('Execute select query')
            result = self.__query(query.getParsedQuery())
            # print('SELECT result', result)
        elif query.getType() == 'DESCRIBE':
            print('Skip describe query')
            result = None
            # print('DESCRIBE result', result)
        elif query.getType() == 'CONSTRUCT':
            print('Execute construct query')
            result = self.__query(query.getParsedQuery())
            # print('CONSTRUCT result', result)
        elif query.getType() == 'ASK':
            print('Execute ask query')
            result = self.__query(query.getParsedQuery())
            # print('CONSTRUCT result', result)
        elif query.getType() == 'UPDATE':
            if query.getParsedQuery() is None:
                query = querystring
            else:
                query = query.getParsedQuery()
            print('Execute update query')
            result = self.__update(query)

        return result

    def __query(self, querystring):
        """Execute a SPARQL select query.

        Args:
            querystring: A string containing a SPARQL ask or select query.
        Returns:
            The SPARQL result set
        """
        return self.store.query(querystring)

    def __update(self, querystring):
        """Execute a SPARQL update query and update the store.

        This method executes a SPARQL update query and updates and commits all affected files.

        Args:
            querystring: A string containing a SPARQL upate query.
        """
        # methods of rdflib ConjunciveGraph
        self.store.update(querystring)
        self.store.commit()
        # methods of MemoryStore to update the file system and git
        self.__updatecontentandsave()
        self.__updategit()
        self.__commit()

        return

    def addquads(self, quads):
        """Add quads to the MemoryStore.

        Args:
            quads: Rdflib.quads that should be added to the MemoryStore.
        """
        self.store.addN(quads)
        self.store.commit()

        return

    def removequads(self, quads):
        """Remove quads from the MemoryStore.

        Args:
            quads: Rdflib.quads that should be removed to the MemoryStore.
        """
        self.store.remove((quads))
        self.store.commit()
        return

    def reinitgraph(self, graphuri):
        """Reset named graph.

        Args:
            graphuri: The URI of a named graph.
        """
        self.store.remove((None, None, None, graphuri))

        for k, v in self.files.items():
            if k == graphuri:
                FileReferenceObject = v
                break

        try:
            content = FileReferenceObject.getcontent()
            self.store.parse(data=''.join(content), format='nquads')
        except:
            print('Something went wrong with file:', self.filepath)
            raise ValueError

        return

    def getgraphcontent(self, graphuri):
        """Get the serialized content of a named graph.

        Args:
            graphuri: The URI of a named graph.
        Returns:
            content: A list of strings where each string is a quad.
        """
        data = []
        context = self.store.get_context(URIRef(graphuri))
        triplestring = context.serialize(format='nt').decode('UTF-8')

        # Since we have triples here, we transform them to quads by adding the graphuri
        # TODO This might cause problems if ' .\n' will be part of a literal.
        #   Maybe a regex would be a better solution
        triplestring = triplestring.replace(' .\n', ' <' + graphuri + '> .\n')

        data = triplestring.splitlines()

        return data

    def getcommits(self):
        """Return meta data about exitsting commits.

        Returns:
            A list containing dictionaries with commit meta data
        """
        return self.repo.getcommits()

    def checkout(self, commitid):
        """Checkout a commit by a commit id.

        Args:
            commitid: A string cotaining a commitid.
        """
        self.repo.checkout(commitid)
        self.__reinit()
        return

    def commitexists(self, commitid):
        """Check if a commit id is part of the repository history.

        Args:
            commitid: String of a Git commit id.
        Returns:
            True, if commitid is part of commit log
            False, else.
        """
        return self.repo.commitexist(commitid)

    def exit(self):
        """Execute actions on API shutdown."""
        return


def sparqlresponse(result, format):
    """Create a FLASK HTTP response for sparql-result+json."""
    print("result type", type(result))
    return Response(
            result.serialize(format=format['format']).decode('utf-8'),
            content_type=format['mime']
            )


def splitinformation(quads, GraphObject):
    """Split quads ."""
    data = []
    graphsInRequest = set()
    for quad in quads:
        graph = quad[3].n3().strip('[]')
        if graph.startswith('_:', 0, 2):
            graphsInRequest.add('default')
            data.append({
                        'graph': 'default',
                        'quad': quad[0].n3() + ' ' + quad[1].n3() + ' ' + quad[2].n3() + ' .\n'
                        })
        else:
            graphsInRequest.add(graph.strip('<>'))
            data.append({
                        'graph': graph.strip('<>'),
                        'quad': quad[0].n3() + ' ' + quad[1].n3() + ' ' + quad[2].n3() + ' ' + graph + ' .\n'
                        })
    return {'graphs': graphsInRequest, 'data': data, 'GraphObject': GraphObject}
