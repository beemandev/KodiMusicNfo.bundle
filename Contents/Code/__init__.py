import os, string, re, unicodedata, sys, urllib, urlparse

NFO_TEXT_REGEX_1 = re.compile(
    r'&(?![A-Za-z]+[0-9]*;|#[0-9]+;|#x[0-9a-fA-F]+;)'
)
NFO_TEXT_REGEX_2 = re.compile(r'^\s*<.*/>[\r\n]+', flags=re.MULTILINE)
RATING_REGEX_1 = re.compile(
    r'(?:Rated\s)?(?P<mpaa>[A-z0-9-+/.]+(?:\s[0-9]+[A-z]?)?)?'
)
RATING_REGEX_2 = re.compile(r'\s*\(.*?\)')

def Start():pass

def GetParentDir(directories):
  parent_dirs = {}
  for d in directories:
    try:
      parent = os.path.split(d)[0]
      parent_dirs[parent] = True
    except:pass
  
  if parent_dirs.has_key(''):
    del parent_dirs['']
  return parent_dirs

#searches for a valid nfo file, loads it up ands returns it
def FindNfo(paths, nfo):
  for path in paths:
    for f in os.listdir(path):
      (fn, ext) = os.path.splitext(f)
      if(fn == nfo and not fn.startswith('.') and ext[1:] == "nfo"):
        nfo_file = os.path.join(path, f)
        nfo_text = Core.storage.load(nfo_file)
        # work around failing XML parses for things with &'s in them. This may need to go farther than just &'s....
        nfo_text = NFO_TEXT_REGEX_1.sub('&amp;', nfo_text)
        # remove empty xml tags from nfo
        Log('Removing empty XML tags from nfo...')
        nfo_text = NFO_TEXT_REGEX_2.sub('', nfo_text)

        nfo_text_lower = nfo_text.lower()
        if nfo_text_lower.count('<'+nfo) > 0 and nfo_text_lower.count('</'+nfo+'>') > 0:
            # Remove URLs (or other stuff) at the end of the XML file
            content = nfo_text.rsplit('</'+nfo+'>', 1)[0]
            nfo_text = '{content}</{nfo}>'.format(content=content,nfo=nfo)

            # likely a kodi nfo file
            try:
                nfo_xml = XML.ElementFromString(nfo_text).xpath('//'+nfo)[0]
            except:
                Log("ERROR: Cant parse %s from XML in %s Skipping!", nfo, nfo_file)
                continue

            # remove empty xml tags
            Log('Removing empty XML tags from nfo...')
            nfo_xml = remove_empty_tags(nfo_xml)
            Log("%s data loaded from file %s", nfo, nfo_file)
            return nfo_xml

def remove_empty_tags(document):
    """
    Removes empty XML tags.

    :param document: An HTML element object.
        see: http://lxml.de/api/lxml.etree._Element-class.html
    :return:
    """
    empty_tags = []
    for xml_tag in document.iter('*'):
        if not(len(xml_tag) or (xml_tag.text and xml_tag.text.strip())):
                empty_tags.append(xml_tag.tag)
                xml_tag.getparent().remove(xml_tag)
    Log('Empty XMLTags removed: {number} {tags}'.format(
        number=len(empty_tags) or None,
        tags=sorted(set(empty_tags)) or ''
    ))
    return document
    
#searches for artist.nfo in Artist folder and adds fields to the metadata  
def ReadArtistNfo(metadata, paths):
  nfo_xml = FindNfo(paths,'artist')
  if nfo_xml:
    add_tag(nfo_xml, metadata.summary, 'biography')
    add_tags(nfo_xml, metadata.genres, 'genre')
    add_tags(nfo_xml, metadata.styles, 'style')
    add_tags(nfo_xml, metadata.moods, 'mood')
    Log('artist fields added from artist.nfo')

#searches for album.nfo in Album folder and adds fields to the metadata
def ReadAlbumNfo(metadata, paths):
  nfo_xml = FindNfo(paths,'album')
  if nfo_xml:
    add_tag(nfo_xml, metadata.summary, 'review')
    add_tag(nfo_xml, metadata.studio, 'label')
    add_tags(nfo_xml, metadata.genres, 'genre')
    add_tags(nfo_xml, metadata.styles, 'style')
    add_tags(nfo_xml, metadata.moods, 'mood')
    Log('album fields added from album.nfo')

def add_tag(nfo_xml, metadata_tag, name):
    try:
        metadata_tag = nfo_xml.xpath(name)[0].text
    except:
        Log('No <{tag}> tag in nfo'.format(tag=name))
        pass

def add_tags(nfo_xml, metadata_tags, name):
    try:
        tags = nfo_xml.xpath(name)
        metadata_tags.clear()
        [metadata_tags.add(t.strip()) for tagXML in tags for t in tagXML.text.split('/')]
    except:
        Log('No <{tag}> tag in nfo'.format(tag=name))
        pass

class KodiArtistNfo(Agent.Artist):
  contributes_to = ['com.plexapp.agents.none']
  primary_provider = False
  persist_stored_files = False
  name = "Kodi Nfo (Artists)"
  
  def search(self, results, media, lang):
    results.Append(MetadataSearchResult(id = 'null', name=media.artist, score = 100))
    
  def update(self, metadata, media, lang, child_guid=None):
    dirs = {}
    
    for a in media.albums:
      for t in media.albums[a].tracks:
        track = media.albums[a].tracks[t].items[0]
        dirs[os.path.dirname(track.parts[0].file)] = True
    
    artist_dirs = GetParentDir(dirs)    
    
    ReadArtistNfo(metadata, artist_dirs) 
    Log("finished")

    
class KodiAlbumNfo(Agent.Album):
  name = "Kodi Nfo (Albums)"
  primary_provider = False
  persist_stored_files = False
  contributes_to = ['com.plexapp.agents.none']
  
  def search(self, results, media, lang):
    results.Append(MetadataSearchResult(id = 'null', score = 100))
    
  def update(self, metadata, media, lang):
    dirs = {}
    
    for t in media.tracks:
        track = media.tracks[t].items[0]
        dirs[os.path.dirname(track.parts[0].file)] = True
    
    ReadAlbumNfo(metadata, dirs) 
    Log("finished")
