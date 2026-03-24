

## Alexandria Biblical
## Cover Generator
## Project Specification & Requirements Document
Project OwnerTim (tim@ltvspot.com)
## Document Version1.0
DateMarch 20, 2026
StatusSpecification — Ready for Development
Parent ProjectAlexandria Cover Designer v2
Catalog Size~211 biblical / apocryphal titles

Alexandria Biblical Cover Generator — Specification v1.0  |  Page 2
Table of Contents
## 1.   Executive Summary
## 2.   Project Overview
## 3.   Input Data: Title Metadata Catalog
## 4.   Requirement 1 — Cover Template System
## 5.   Requirement 2 — Automated Text Placement
-   Requirement 3 — AI Image Prompt Generation
-   Requirement 4 — AI Image Generation
## 8.   Requirement 5 — Final Cover Assembly
## 9.   Technical Architecture
-   Reference: How the Current Tool Handles Prompt Generation
## 11.   Glossary

Alexandria Biblical Cover Generator — Specification v1.0  |  Page 3
## 1. Executive Summary
This  document  specifies  the  requirements  for  the  Alexandria  Biblical  Cover  Generator,  a  new  web
application  forked  from  the  existing  Alexandria  Cover  Designer  v2.  Where  the  current  tool  composites
AI-generated   illustrations   into   pre-designed   ornamental   PDF   cover   frames,   this   new   tool   takes   a
fundamentally  different  approach:  it  generates  complete  book  covers  from  scratch,  using  only  the  title
metadata as input.
The tool must handle approximately 211 biblical, apocryphal, and ancient religious titles. For each title,
the system must be capable of:
•Rendering a complete cover layout (front, spine, back) from a reusable template, with all text fields
automatically populated from the metadata catalog.
•Generating content-aware AI image prompts — both base style prompts and wildcard style variants —
that are visually relevant to each title's specific subject matter.
•Generating AI cover illustrations via image generation APIs (same providers as the current tool:
OpenRouter, Google Gemini, etc.).
•Assembling the final cover by compositing the generated illustration into the template layout.
The  end  result  is  a  tool  where  a  user  can  select  any  title  from  the  catalog,  click  generate,  and  receive
multiple  complete  cover  variations  —  each  with  correct  typography,  a  unique  AI  illustration  matching  the
book's content, and a print-ready layout — with no manual design work required.

Alexandria Biblical Cover Generator — Specification v1.0  |  Page 4
## 2. Project Overview
2.1 Relationship to the Current Tool
The existing Alexandria Cover Designer v2 was built for a catalog of ~99 classic literature titles that already
had  professionally  designed  cover  PDFs.  The  tool's  primary  job  was  to  replace  the  placeholder  medallion
illustration inside those existing covers with AI-generated art. It did not need to handle typography, layout, or
spine/back-cover content — all of that was baked into the original designer's PDFs.
The new Biblical Cover Generator serves a catalog of ~211 titles that do not have pre-designed covers.
Therefore  the  tool  must  handle  the  entire  cover  creation  pipeline  end-to-end:  template  design,  text
placement, image generation, and final assembly.
2.2 What Carries Over from the Current Tool
•The web application framework (Node.js frontend, Python backend).
•The image generation pipeline (OpenRouter API integration, model selection, multi-variant generation).
•The prompt library architecture (base prompts + wildcard prompts + style anchors).
•The genre-aware rotation system (genre-to-prompt mapping, scene pool building, auto-rotation).
•The UI patterns (title selector, variant grid, iterate/review workflow).
## 2.3 What Is New
•A cover template system — defining the full-cover layout (front, spine, back) as a reusable,
parameterized template.
•Automated text placement — rendering title, subtitle, author, spine text, and back-cover description
onto the template from metadata.
•Content-aware prompt generation — automatically building enrichment data and image generation
prompts for all 211 titles from metadata + optional external research.
•A cover assembly pipeline — compositing the AI illustration into the correct region of the typeset
cover template to produce the final output.
## 2.4 Scope
This specification covers the requirements and expected behavior of the system. It describes what the tool
must do, not how to implement it (except in Section 10, where the current tool's prompt generation system is
documented as a reference for the new implementation).

Alexandria Biblical Cover Generator — Specification v1.0  |  Page 5
## 3. Input Data: Title Metadata Catalog
The primary input to the system is a metadata catalog containing detailed information for each of the ~211
titles. This catalog is provided as a PDF document (00 - Combined Biblical Titles Metadata.pdf) and must be
parsed and stored in a structured format (e.g., JSON) for use by the application.
## 3.1 Available Metadata Fields Per Title
Each  title  entry  in  the  catalog  contains  the  following  fields.  All  fields  are  required  for  the  tool  to  function
correctly.
FieldDescriptionUsed By
TitleMain title of the book (e.g., 'Gospel of
## Bartholomew')
Front cover, spine
SubtitleExtended subtitle describing the book's themesFront cover
AuthorAttribution (e.g., 'Traditionally attributed to
Bartholomew the Apostle')
Front cover, spine
## Back Cover
## Description
Marketing/descriptive text for the back cover
(multiple paragraphs, includes a pull quote)
Back cover
## Main Book
## Description
Detailed description of the book's contents and
themes
Prompt generation
(enrichment source)
## Audiobook
## Description
Alternate description (often more concise)Prompt generation
## (supplementary)
## Ingram Spark
## Keywords
Semicolon-separated keyword list for
discoverability
Genre classification,
prompt generation
## Three Potential
## Cover Ideas
Three ranked cover scene descriptions with
reasoning
Scene pool for prompt
generation (primary source)
## 3.2 Sample Title Entry
Below is a representative example of what the metadata contains for a single title:
Title: Gospel of Bartholomew
Subtitle: The Lost Apocryphal Text of Hidden Biblical Mysteries, Angelic Revelations & The Descent into the
## Underworld
Author: Traditionally attributed to Bartholomew the Apostle
Back Cover: [Pull quote + 2 paragraphs of marketing text]
Main Description: [5+ paragraphs covering content, themes, historical context]
Keywords: Gospel of Bartholomew, apocryphal texts, hidden biblical mysteries, ...
## Cover Ideas:
(Rank 1) A lone, illuminated figure standing at the edge of a fiery chasm, pointing toward a massive shadowed
entity bound in chains.
(Rank 2) Glowing pair of ancient bronze gates bursting open with radiant light.
(Rank 3) Ancient tattered scroll on a stone table illuminated by a shaft of divine light.

Alexandria Biblical Cover Generator — Specification v1.0  |  Page 6
## 3.3 Catalog Scope
The catalog contains approximately 211 titles. The numbering in the source PDF goes up to #307 but has
gaps  (some  numbers  are  skipped).  The  complete  title  list  spans  biblical  apocrypha,  Gnostic  texts,
pseudepigrapha, Dead Sea Scrolls material, early Christian writings, and related ancient manuscripts.

Alexandria Biblical Cover Generator — Specification v1.0  |  Page 7
## 4. Requirement 1 — Cover Template System
The  system  must  use  a  reusable  cover  template  that  defines  the  complete  layout  for  a  print-ready  book
cover.  This  template  must  be  designed  once  and  then  automatically  populated  with  each  title's  specific
content.
## 4.1 Template Structure
A  single  cover  file  (as  used  by  Lightning  Source  /  Ingram  Spark)  consists  of  three  panels  laid  out  side  by
side:
•Back Cover (left panel) — Contains the back-cover description text, pull quote, barcode area, and
optional publisher logo.
•Spine (center strip) — Contains the title and author name, rotated vertically.
•Front Cover (right panel) — Contains the main title, subtitle, author name, and the AI-generated cover
illustration.
## 4.2 Template Design Requirements
The template must establish a consistent visual identity across all 211 titles. The following elements must be
defined in the template:
## 4.2.1 Visual Identity
•Color scheme: A consistent palette to be used across all covers (e.g., the existing Alexandria series
uses navy blue + gold). The specific palette is a design decision, but it must be defined in the template
and applied uniformly.
•Decorative elements: Any ornamental borders, frames, dividers, or background patterns that form
part of the series identity.
•Illustration region: A clearly defined area on the front cover where the AI-generated illustration will be
placed. This could be a circular medallion (as in the current tool), a rectangular region, a full-bleed
background, or any other defined shape.
## 4.2.2 Typography Zones
The template must define precise placement zones for each text element, including:
•Front cover — Main Title: Position, maximum width, font family, font size range (with rules for scaling
long titles), color, and alignment.
•Front cover — Subtitle: Position, maximum width, font, size, color. Must accommodate subtitles of
varying length (some are 1 line, some are 3+ lines).
•Front cover — Author: Position, font, size, color.
•Spine — Title: Vertical text, font, size, color. Must handle titles of varying length.
•Spine — Author: Vertical text, font, size, color.
•Back cover — Pull Quote: Position, font (typically italic), size, color.
•Back cover — Description: Position, maximum width, font, size, line spacing, color. Must
accommodate multi-paragraph text of varying length.

Alexandria Biblical Cover Generator — Specification v1.0  |  Page 8
•Back cover — Barcode area: Reserved blank area for ISBN barcode placement.
## 4.2.3 Dimension Requirements
•The template must support standard print-on-demand dimensions as required by Lightning Source /
## Ingram Spark.
•Spine width must be variable (calculated from page count) or configurable per title.
•The template must include bleed areas as required by the printer (typically 0.125 inches on all sides).
## 4.3 Template Format
The  template  must  be  stored  in  a  format  that  allows  programmatic  text  insertion  and  image  compositing.
Acceptable  approaches  include  a  PDF  template  with  defined  form  fields  or  coordinate-based  regions,  an
SVG  template,  a  programmatic  layout  (e.g.,  ReportLab/Python  or  HTML-to-PDF),  or  similar.  The  specific
format is an implementation decision.
## 4.4 Deliverable
At least one fully designed, production-quality cover template that can be reused for all 211 titles. Additional
template variants (different visual themes) are welcome but not required for the initial release.

Alexandria Biblical Cover Generator — Specification v1.0  |  Page 9
## 5. Requirement 2 — Automated Text Placement
The  system  must  automatically  populate  the  cover  template  with  each  title's  text  content,  producing  a
typographically correct cover layout without any manual intervention.
5.1 Text Fields to Populate
FieldSourcePlacementNotes
Main Titlemetadata.titleFront cover (prominent),
## Spine
Must scale font size for long titles
Subtitlemetadata.subtitleFront cover (below title)Varies from 1 to 3+ lines
Authormetadata.authorFront cover, SpineSome are long attributions
## Spine Textmetadata.title +
metadata.author
Spine (vertical)Title + author, rotated 90°
## Back
## Description
metadata.back_cov
er_description
Back coverMulti-paragraph, includes pull
quote
## 5.2 Typography Requirements
•Font consistency: All titles in the series must use the same font family/families. The specific font(s)
are a design decision but must be defined in the template.
•Dynamic font scaling: Titles vary significantly in length (from single words like 'Marsanes' to multi-line
titles like 'Apocryphon of John (Secret Book of John)'). The system must automatically scale font sizes
to fit within the designated area without overflow or truncation.
•Text wrapping: Subtitles and back-cover descriptions must wrap correctly within their defined areas.
•Typographic hierarchy: The visual hierarchy must be clear — title is most prominent, subtitle
secondary, author tertiary.
•Spine text legibility: Spine text must remain legible at the actual printed spine width. For very thin
spines, consider omitting the author or abbreviating.
•Special characters: The system must handle special characters that appear in some titles (e.g., em
dashes, ampersands, Roman numerals, parenthetical notes, diacritics in transliterated names).
## 5.3 Back Cover Layout
The back cover has the most complex text layout. It must accommodate:
•An opening pull quote (typically 1-3 sentences in italics, with attribution).
•Multiple paragraphs of descriptive text.
•An optional bulleted list of chapter highlights (present in some titles).
•A closing call-to-action paragraph.
•A reserved area for the ISBN barcode (typically bottom-right or bottom-center).

Alexandria Biblical Cover Generator — Specification v1.0  |  Page 10
The system must handle varying description lengths — some titles have 3 short paragraphs, others have 6+
substantial paragraphs with bullet lists. Overflow handling (e.g., truncation with ellipsis, font size reduction,
or scrollable preview) must be defined.

Alexandria Biblical Cover Generator — Specification v1.0  |  Page 11
- Requirement 3 — AI Image Prompt Generation
The system must be able to generate high-quality, content-relevant AI image generation prompts for each of
the 211 titles. This is the most intellectually complex requirement and the one most critical to cover quality. A
generic or irrelevant cover illustration would defeat the purpose of the tool.
This section describes what is required. Section 10 documents how the current Alexandria Cover Designer
solves a similar problem, as a reference for implementation.
## 6.1 Enrichment Data Generation
Before prompts can be generated, each title needs structured enrichment data — a set of content-specific
details  that  the  prompt  system  uses  to  create  relevant  illustrations.  This  enrichment  data  must  be  derived
from the metadata catalog (and optionally supplemented with external research).
## 6.1.1 Required Enrichment Fields Per Title
•Genre / Category: Classification of the text (e.g., 'Gnostic Cosmology', 'Apocalyptic Vision',
'Apocryphal Gospel', 'Wisdom Literature', 'Pseudepigraphal Narrative').
•Era / Time Period: The historical setting or period the text describes (e.g., 'Early Christian period,
1st-2nd century CE', 'Pre-flood antediluvian era').
•Emotional Tone / Mood: The dominant mood of the text (e.g., 'mystical awe', 'apocalyptic dread',
'contemplative wisdom', 'dramatic spiritual warfare').
•Key Characters: Named figures with brief visual descriptions (e.g., 'Bartholomew — an apostle in
humble robes, bold and questioning', 'Beliar — prince of darkness, bound in chains of fire').
•Iconic Scenes (3-5): Vivid, visually specific scene descriptions drawn from the text's actual content.
These become the core of the image generation prompts.
•Visual Motifs: Recurring visual symbols (e.g., 'gates of brass', 'celestial staircase', 'burning scroll',
'desert wilderness').
•Setting / Location: Primary physical settings (e.g., 'the underworld', 'heavenly throne room', 'Egyptian
desert', 'celestial spheres').
•Color Palette Suggestion: Thematic color direction (e.g., 'deep crimson and gold', 'ethereal
silver-blue', 'earth tones and firelight').
6.1.2 Sources for Enrichment Data
The metadata catalog already contains rich source material for generating enrichment data:
•Three Potential Cover Ideas — These are the highest-quality source. Each title has three ranked,
vivid scene descriptions with reasoning. These should form the basis of the iconic_scenes field.
•Main Book Description — Contains detailed content summaries, key themes, character names, and
plot points.
•Back Cover Description — Often includes evocative language, pull quotes, and thematic keywords.
•Ingram Spark Keywords — Useful for genre classification and thematic tagging.
•Audiobook Description — Supplementary content that may contain unique phrasing or scene
descriptions.

Alexandria Biblical Cover Generator — Specification v1.0  |  Page 12
## 6.1.3 Optional: External Research Enrichment
For titles where the metadata alone may not provide sufficient visual detail (e.g., very short or fragmentary
texts), the system could optionally use web search or an LLM to research the actual content of the ancient
text  and  extract  additional  scene  descriptions,  character  details,  and  visual  motifs.  This  is  not  strictly
required if the metadata is rich enough, but would improve prompt quality for edge cases.
## 6.2 Prompt Architecture
The  system  must  generate  image  prompts  using  a  structured  architecture  that  separates  scene  content
(what  to  depict)  from  artistic  style  (how  to  depict  it).  This  separation  enables  generating  multiple  visual
variations of the same scene.
## 6.2.1 Base Prompts
Base  prompts  define  the  primary  artistic  styles  for  the  series.  Each  base  prompt  is  a  template  containing
placeholders that get filled with title-specific content. The system needs a curated set of base prompt styles
(5-10  recommended)  that  work  well  for  biblical/ancient  religious  subject  matter.  Examples  of  appropriate
base styles might include:
•Classical oil painting (Renaissance/Baroque)
•Illuminated manuscript style
•Gothic romantic atmosphere
•Byzantine iconographic
•Dramatic chiaroscuro
Each  base  prompt  template  must  include  at  minimum  the  placeholders  {SCENE},  {MOOD},  and  {ERA}
which are resolved at generation time from the enrichment data.
## 6.2.2 Wildcard Prompts
Wildcard  prompts  provide  additional  stylistic  variety  beyond  the  base  set.  They  define  alternative  artistic
techniques  or  visual  treatments.  The  system  needs  15-30  wildcard  styles  that  produce  distinctive,  visually
interesting  results.  These  use  the  same  placeholder  system  as  base  prompts  but  apply  different  artistic
techniques (e.g., copper engraving, watercolor wash, woodcut print, stained glass, mosaic, fresco).
6.2.3 Genre-Aware Assignment
Not  all  styles  work  equally  well  for  all  types  of  content.  The  system  must  map  genres  to  preferred  prompt
styles.  For  example,  'Apocalyptic  Vision'  titles  might  prefer  dramatic,  high-contrast  styles,  while  'Wisdom
Literature' titles might prefer contemplative, softer styles. The prompt assignment system must:
•Assign genre-appropriate base prompts preferentially.
•Use wildcard prompts to provide variety without genre mismatch.
•Ensure each variant in a multi-variant generation uses a different scene from the enrichment pool.
## 6.3 Content Relevance Rule
This is a hard requirement inherited from lessons learned on the current tool:
Every generated cover illustration MUST be visually relevant to the actual content of the specific title.
Generic religious imagery (e.g., 'a glowing scroll' for every title) is unacceptable. Someone familiar with the text

Alexandria Biblical Cover Generator — Specification v1.0  |  Page 13
should be able to recognize the scene depicted on the cover. This requirement is what makes the enrichment
data and scene pool system essential.
## 6.4 Deliverable
•A complete enrichment dataset for all ~211 titles (stored as structured JSON).
•A curated prompt library with base and wildcard prompt templates.
•A genre-to-prompt mapping configuration.
•The prompt generation engine that resolves templates + enrichment into final API-ready prompts.

Alexandria Biblical Cover Generator — Specification v1.0  |  Page 14
- Requirement 4 — AI Image Generation
The system must generate AI illustrations by sending the composed prompts to image generation APIs. This
requirement is largely inherited from the existing tool.
## 7.1 Supported Providers
The system must support the same image generation providers as the current tool:
•OpenRouter (primary) — Routes to models like Google Gemini Image, Flux, DALL-E, Stable Diffusion.
•Google Gemini (direct) — Direct API access for Gemini image generation models.
•Fallback providers — Fal, OpenAI direct, or other providers as needed.
## 7.2 Generation Workflow
•User selects a title from the catalog.
•User selects one or more image generation models.
•User selects the number of variants to generate (default: 10).
•System auto-assigns prompts to variants using genre-aware rotation (see Section 6.2.3).
•System sends all generation jobs to the selected API(s).
•Results are displayed in a grid for review and selection.
## 7.3 Image Output Requirements
•Resolution: Generated images must be high enough resolution for print (minimum 300 DPI at the
target illustration size on the cover). The exact pixel dimensions depend on the template's illustration
region.
•Format: PNG or high-quality JPEG.
•Aspect ratio: Must match the illustration region defined in the template (e.g., square for a medallion,
portrait for a tall rectangle, landscape for a banner).
•No text in images: Prompts must include negative instructions to prevent the AI from rendering text,
letters, or words in the generated illustration (all text is handled by the template system).
•No borders/frames in images: Prompts must instruct the AI to generate scene-only illustrations
without decorative borders, frames, or ornaments (those are part of the template).

Alexandria Biblical Cover Generator — Specification v1.0  |  Page 15
## 8. Requirement 5 — Final Cover Assembly
The  system  must  combine  the  typeset  cover  template  (with  all  text  placed)  and  the  selected  AI  illustration
into a single, print-ready cover file.
## 8.1 Assembly Process
•Take the populated template (with title, subtitle, author, spine text, back cover description all placed).
•Take the user-selected AI illustration.
•Composite the illustration into the template's designated illustration region.
•Output the final assembled cover.
## 8.2 Compositing Requirements
•Precise placement: The illustration must be placed exactly within the defined illustration region, with
correct scaling and cropping.
•Edge handling: The transition between the illustration and the template's decorative elements must
be clean (e.g., feathered edges if using a medallion, hard crop if using a rectangular region).
•No frame damage: The template's decorative elements (borders, ornaments, etc.) must remain
perfectly intact after compositing. This was a major source of bugs in the current tool and must be
handled correctly from the start.
•Layer order: Decorative frame elements must render on top of the illustration, not behind it (so the
frame visually 'contains' the art).
## 8.3 Output Formats
•PDF (primary) — Print-ready, CMYK color space, with bleed and trim marks. This is the format
submitted to Lightning Source / Ingram Spark.
•High-resolution PNG/JPEG — For web use, previews, and marketing materials.
•Preview thumbnail — Lower resolution version for in-app display during the review workflow.
## 8.4 Batch Capability
The  system  should  support  batch  operations:  generating  covers  for  multiple  titles  in  sequence  without
manual intervention. This enables producing covers for all 211 titles efficiently.

Alexandria Biblical Cover Generator — Specification v1.0  |  Page 16
## 9. Technical Architecture
The new tool is forked from the existing Alexandria Cover Designer v2. The following describes the inherited
architecture and the expected modifications.
## 9.1 Inherited Stack
•Frontend: Single-page application (SPA) using client-side JavaScript, HTML, CSS. Hash-based
routing. Pages include: title selector, iterate (generation), review, batch, dashboard.
•Backend: Python modules for image generation API calls, prompt composition, catalog management,
and (now) cover template rendering + text placement + assembly.
•Deployment: Railway (auto-deploy from GitHub push).
•Storage: Google Drive integration for saving outputs. Local filesystem as fallback.
## 9.2 New Components Required
•Metadata Parser: Converts the PDF metadata catalog into structured JSON (one-time or on-demand).
•Enrichment Generator: Processes raw metadata into the structured enrichment format required by
the prompt system.
•Template Renderer: Takes a template definition + title metadata and produces a typeset cover layout
(with all text placed, illustration region empty).
•Cover Assembler: Composites the AI illustration into the typeset cover to produce the final output.
## 9.3 Data Flow
The end-to-end pipeline flows as follows:
## Ste
p
InputProcessOutput
1Metadata PDFParse & structuretitle_catalog.json
2title_catalog.jsonEnrichment generationtitle_catalog_enriched.json
3Enriched catalog +
template
Template renderingTypeset cover (text placed, no illustration)
4Enriched catalog +
prompt library
Prompt generationAPI-ready image prompts
5Image promptsAI image generationGenerated illustrations
6Typeset cover +
selected illustration
Cover assemblyFinal print-ready cover (PDF + image)

Alexandria Biblical Cover Generator — Specification v1.0  |  Page 17
- Reference: How the Current Tool Handles Prompt
## Generation
This  section  documents  the  existing  Alexandria  Cover  Designer's  prompt  generation  system  in  detail.  It  is
provided as a reference and potential starting point for the new tool's implementation. The new tool should
reuse or adapt this architecture rather than building from scratch.
## 10.1 Enrichment Data Structure
The  current  tool  stores  enrichment  data  in  config/book_catalog_enriched.json.  Each  book  entry
contains a nested enrichment object with the following fields:
•genre — e.g., 'Romantic Fiction', 'Gothic Horror', 'Philosophical Literature'
•era — e.g., 'Early 20th century, specifically 1900s'
•emotional_tone — e.g., 'romantic longing, cultural awakening, quiet rebellion'
•setting_primary — e.g., 'Florence, Italy and the English countryside'
•setting_details — Array of 4+ detailed location descriptions
•key_characters — Array of 5+ character descriptions with visual detail (e.g., 'George Emerson — a
handsome young man with tousled dark hair and an earnest expression')
•iconic_scenes — Array of 5+ vivid scene descriptions (e.g., 'Lucy Honeychurch stands on the balcony
of the Pension Bertolini, gazing out over the Arno River as the sun sets')
•visual_motifs — Array of recurring visual symbols
•symbolic_elements — Array of thematic symbols
•color_palette_suggestion — Suggested color direction
•art_period_match — Suggested art historical period
For the new biblical catalog, a similar enrichment structure must be generated. The metadata's 'Three Potential
Cover Ideas' field maps directly to iconic_scenes. The keywords map to genre classification. The descriptions
provide source material for characters, settings, and motifs.
## 10.2 Prompt Template System
Prompts are stored in config/prompt_library.json as template strings with placeholders. The system
supports 7 placeholder types:
PlaceholderResolved FromExample Value
{SCENE}enrichment.iconic_scenes (rotated
per variant)
'Bartholomew stands at the edge of a fiery
chasm, pointing toward Beliar in chains'
{MOOD}enrichment.emotional_tone'apocalyptic dread and divine triumph'
{ERA}enrichment.era'Early Christian period, 1st-2nd century CE'
{TITLE}metadata.title'Gospel of Bartholomew'
{AUTHOR}metadata.author'Bartholomew the Apostle'

Alexandria Biblical Cover Generator — Specification v1.0  |  Page 18
10.3 Base vs. Wildcard Prompt Example
Base Prompt Example (Romantic Realism style):
"{SCENE}. Painted as rich Victorian storybook color plate — opaque gouache with fine ink outlines,
dense  illustration  filling  every  inch,  saturated  colors,  layered  depth  from  foreground  to
atmospheric  background.  Color  direction:  sunlit  gold,  rose-crimson,  glowing  peach.  Mood:  {MOOD}.
Era: {ERA}."
Wildcard Prompt Example (Dramatic Graphic Novel style):
"{SCENE}. Bold crosshatched ink on cream board — stark amber/black palette, graphic novel poster
art, dramatic silhouettes, amber spotlight, ink splatter energy. Mood: {MOOD}. Era: {ERA}."
At  generation  time,  {SCENE}  is  replaced  with  a  specific  scene  from  the  title's  enrichment  data  (e.g.,
'Bartholomew confronts Beliar, prince of darkness, in the depths of the underworld, chains of fire binding the
shadowed entity'). Each variant gets a different scene from the pool.
## 10.4 Scene Pool & Rotation System
The current tool's buildScenePool() function collects scenes from multiple enrichment fields to create a
diverse pool:
•Primary source: enrichment.iconic_scenes (typically 5 scenes)
•Secondary: character-based scenes, setting descriptions, visual motifs
•The pool is deduplicated and provides 5-10 unique scenes per title
When  generating  N  variants,  the  system  assigns  scenes  round-robin  from  the  pool,  ensuring  each  variant
depicts a different moment or perspective from the text.
10.5 Genre-Aware Rotation
The current tool maps each genre to preferred prompt styles via a GENRE_PROMPT_MAP configuration. For a
10-variant generation:
•Variants 1-5: Use genre-matched base prompts (e.g., Gothic Horror titles get 'Gothic Atmosphere'
base style).
•Variants 6-10: Use shuffled wildcard prompts from the genre's preferred wildcard pool.
•Each variant gets a unique scene from the scene pool (no two variants show the same scene).
•A Fisher-Yates shuffle ensures variety across generations, with anti-repeat logic.
10.6 Potential Approach for the Biblical Catalog
The new tool can reuse this architecture with biblical-specific adaptations:
•Enrichment generation: The metadata's 'Three Potential Cover Ideas' field provides pre-written iconic
scenes for every title. The 'Main Book Description' and 'Audiobook Description' provide character
names, settings, and themes. An LLM-assisted enrichment pipeline could parse these into the
structured format, with optional web research to fill gaps.
•Genre mapping: Define biblical-specific genres (Gnostic Cosmology, Apocalyptic Vision, Apocryphal
Gospel, Pseudepigraphal Narrative, Wisdom Literature, Hagiography, etc.) and map each to preferred

Alexandria Biblical Cover Generator — Specification v1.0  |  Page 19
prompt styles.
•Base prompts: Adapt existing prompts or create new ones tuned for ancient/biblical subject matter
(illuminated manuscript, Byzantine icon, Renaissance religious painting, etc.).
•Wildcard prompts: Add styles appropriate for the genre (stained glass, mosaic, fresco, coptic art,
Dead Sea Scroll aesthetic, etc.).
•Scene pool: Each title's 3 cover ideas + extracted scenes from descriptions = 5-8 unique scenes per
title, sufficient for 10-variant generation with no repeats.

Alexandria Biblical Cover Generator — Specification v1.0  |  Page 20
## 11. Glossary
## Base Prompt
A prompt template defining a primary artistic style (e.g., 'oil painting', 'illuminated manuscript'). Used for the
first half of generated variants.
## Wildcard Prompt
A  prompt  template  defining  an  alternative  or  experimental  artistic  style.  Used  for  the  second  half  of
generated variants to provide stylistic diversity.
## Enrichment Data
Structured  metadata  derived  from  raw  title  information,  containing  genre,  era,  mood,  characters,  scenes,
motifs, and settings. Used to populate prompt placeholders.
## Scene Pool
A  deduplicated  collection  of  vivid  scene  descriptions  for  a  given  title,  drawn  from  enrichment  data.  Each
variant in a generation run draws from this pool.
Genre-Aware Rotation
The  system  that  maps  a  title's  genre  to  preferred  prompt  styles,  ensuring  stylistically  appropriate  cover
illustrations.
## Compositor
The  component  that  places  an  AI-generated  illustration  into  the  designated  region  of  a  cover  template,
handling scaling, cropping, edge blending, and layer ordering.
## Template
A  reusable  cover  layout  definition  specifying  the  visual  identity,  typography  zones,  illustration  region,  and
decorative elements for the series.
## Variant
A single generated cover illustration. Multiple variants (typically 10) are generated per title to give the user
options.
OpenRouter
An API aggregator that provides access to multiple image generation models (Gemini, Flux, DALL-E, etc.)
through a single endpoint.
## Lightning Source / Ingram Spark
The  print-on-demand  service  used  to  produce  physical  copies.  Covers  must  meet  their  dimension,  bleed,
and file format specifications.
End of Specification — Alexandria Biblical Cover Generator v1.0