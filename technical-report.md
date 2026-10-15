# Technical Report

Numan Bekir Özçelik, September 2026

## 1. Problem and approach

The user gives an image URL. The application names the object in the image,
generates keywords, collects information about the object from the web and
records it. The loop runs until the user quits, and earlier turns affect later
searches.

The problem splits into three parts: getting an object name from the image,
getting keywords from the object, and putting together meaningful text from
the object and the keywords. The first two are solved with a single vision
model, the third with information retrieval and text generation rules I wrote
myself.

Input is treated as untrusted. A URL is accepted only with the http and https
schemes, no requests are sent to internal network or local machine addresses,
redirects are followed by hand and every hop goes through the same check. The
download is streamed and cut off at twenty megabytes, and a server that
returns a web page instead of an image gets its own message. File content is
validated by actual decoding, not by extension. The orientation of phone
photos is corrected, all images are converted to RGB, and for multi-frame
formats the first frame is used. Very small images are rejected and very large
ones are downscaled to save memory. Every error comes back as a one-sentence
message that tells the user what to do, and the loop continues.

## 2. Object detection

The model is the open source CLIP ViT-B/32. It was trained on hundreds of
millions of image and caption pairs so that matching pairs end up close in
vector space and non-matching pairs end up far apart. The class of an image is
found by computing the cosine similarity with the text vectors of the
candidate names and applying softmax. The class list lives outside the model,
in the object names file in the data folder. It consists of the 1200 category
names of the LVIS dataset and their Turkish equivalents. Adding a line to the
list makes a new object recognizable without changing the code.

I wrote the inference pipeline myself. It covers encoding text with several
prompt templates and averaging them, averaging the features of the full image
and a center crop, the cosine and softmax computation, and choosing words from
the theme scores. Only the model weights and the image preprocessing come from
the library.

The model choice is based on measurement. Three candidates were compared
during development. The closed-set YOLO11n model is limited to eighty classes.
For an object outside its scope it either stays silent or forces the nearest
class. In the measurement it classified a violin image as scissors. The
open-vocabulary YOLO-World model suffers from score dilution as the name list
grows: it found the same object in a list of twenty names but not in a list of
a thousand. Location is also not needed here, since the image is assumed to
have a single object in the foreground. CLIP can tell apart thousands of
names, the same feature vector gives both the object name and the themes, and
it runs in fifty milliseconds per image on the CPU.

Object and theme classification are two separate views of the same image. On
product photos with a white background the object list can be wrong on fine
distinctions while the theme list stays right on the broad concept. That is
why there is an agreement rule. If the object confidence is below 0.5, and the
name of one of the strongest themes is also in the object list, and that name
is among the object candidates, that candidate is chosen as the object. The
rule does not run when confidence is high.

The measurement was done with a test set of fourteen images. The set has seven
everyday objects, plus a violin, a camera, a teapot, a cluttered scene and an
unrelated image. Of the twelve images with a single object in the foreground,
eleven were recognized correctly. The cluttered scene and the unrelated image
stayed below the low confidence threshold and got the "not sure" message.

## 3. The classifier I trained

A small model I trained was added next to the zero-shot classification. It is
a single linear layer that takes the 512-dimensional unit vector produced by
the CLIP image encoder as input. The image encoder stays frozen and only this
layer is trained. This is the only reasonable option that trains in minutes on
a CPU and does better than zero-shot. A convolutional network trained from
scratch would take days and still do worse.

The dataset is Caltech-101. It has a hundred and one object classes and about
nine thousand images, and it is downloaded through torchvision. The faces and
background classes were removed, and since the classes are imbalanced, at most
sixty images were taken from each class. That left 5173 images and 99 classes.
Twenty percent of each class was set aside for validation.

The training code is in the training folder. The feature extraction script
encodes the images and writes them to a single file, and the training script
trains the classifier. I wrote the training loop myself: cross-entropy loss,
the Adam optimizer, batch size 128, at most three hundred epochs, and early
stopping if the validation loss does not improve for ten epochs.

The learning rate and weight decay were chosen with a sweep. The sweep script
tried four learning rates and three decay values on the same training and
validation sets. The results are validation accuracy.

| Learning rate | Decay 0 | Decay 0.0001 | Decay 0.001 |
|---|---|---|---|
| 0.001 | 0.955 | 0.935 | 0.806 |
| 0.005 | 0.954 | 0.936 | 0.803 |
| 0.01 | 0.953 | 0.935 | 0.806 |
| 0.02 | 0.953 | 0.934 | 0.792 |

Weight decay is what matters, the learning rate only changes how fast training
converges. Accuracy drops as decay goes up, because the input vectors have
unit length and the weights need to grow to separate the classes.

Accuracy is not the only criterion. The application uses the classifier's
opinion according to its confidence, so the confidences need to mean
something. The confidence of wrong predictions was also measured on the same
validation set.

| Decay | Accuracy | Average confidence on wrong predictions | Wrong with confidence above 0.8 |
|---|---|---|---|
| 0 | 0.953 | 0.64 | 21 percent |
| 0.0001 | 0.935 | 0.27 | 0 percent |
| 0.001 | 0.806 | 0.05 | 0 percent |

The model without decay memorizes the training examples and gives high
confidence even when it is wrong: a fifth of its mistakes come with confidence
above 0.8. In the application such an opinion could replace the correct
zero-shot answer with a wrong one. In the measurement it turned a teapot image
into a jug. Decay 0.0001 loses two points of accuracy, but confidence stays
low on wrong predictions and none of them pass the threshold. The chosen
values are learning rate 0.01 and decay 0.0001. With this setting early
stopping kicks in around epoch seventy. Training accuracy is 97 percent and
validation accuracy 93.5 percent, while zero-shot gets 86 percent on the same
set. The seven-point gap shows what training on in-domain data adds to the
general model.

In the application the classifier is a second opinion. Its classes are linked
to the names in the object list through a mapping file, and 57 of the 99
classes have a match. When zero-shot is not confident, the classifier's answer
is checked. If the answer is among the zero-shot candidates, the two opinions
agree and 0.5 confidence is enough. If not, 0.8 confidence is needed on its
own. In the measurement these two thresholds picked the right answer for a
phone image and did not let the wrong jug answer through for the teapot image.
When zero-shot is confident it is left alone, so the 1200-name coverage is
kept. When both opinions give the same answer it counts as a confirmation:
confidence is raised to the classifier's confidence and the theme agreement
rule does not run. Which opinion was chosen is written to the record and to
the details.

Limitation: the Caltech classes cover only part of the objects in the test
set, and for the rest the classifier has no opinion. The model file is small
and comes with the repository. The dataset does not, the training script
downloads it again.

## 4. Keywords

The approach is to extract features from the image and compare them with
predefined attributes. The theme map file has 484 theme concepts. Each concept
has an English name and Turkish keywords. The image vector is compared with
these themes. Words are taken from themes that are within fifteen percent of
the best theme and above an absolute threshold. One word is taken from each
theme first, so the list does not lock onto a single theme. The object's own
name is not repeated as a keyword. If the threshold leaves fewer than three
words, the list is filled up to three from the next themes.

The theme list was not written by intuition. I extracted the WordNet hypernym
chains of each of the 1200 names in the object list and counted how many
objects each concept is an ancestor of. A small number of concepts cover most
of the objects: food is the ancestor of two hundred objects, container of a
hundred and seventy-two, clothing of ninety-seven. Concepts were picked from
this sorted list with two conditions: they must cover many objects and they
must add value to the search query. The broadest concepts at the top of the
list, such as device, covering and solid, were deliberately left out because
they fail the second condition: for a bottle opener the word device adds
nothing to a search. Abstract concepts like event and action were dropped
because they do not fit a vocabulary of photos. Objects whose chain only
passes through these excluded concepts got theme entries under their own
names. The Turkish values are search language, not textbook categories:
phrases that can be searched on their own, like fire safety and public
transport, were chosen. The current map has 153 concept entries and 331
entries that match object names.

The words are specific to the image. The same object can get different words
in different images, which makes the chat context more distinctive.

## 5. Search intent

A Turkish search sentence is built from the object name, the keywords and the
context with rule-based natural language generation. Each keyword has a role
in the word roles file. Attribute and material words go in front as
adjectives. Component words take the suffix lı, li, lu or lü according to
vowel harmony. Usage words are listed with the conjunction "ve". Family and
domain words do not go into the query, because the object name already carries
that information. If opposing attributes such as women's and men's come
together, neither goes into the query.

The object name is pluralized, and in compound nouns the plural suffix goes
between the stem and the possessive suffix. For a single-word object, a usage
word forms a compound noun. If the previous object in the context shares its
last word, the two names are merged into one compound. In the food family the
sentence ends with the word for recipes. Vowel harmony, consonant softening
and the possessive and plural suffixes are computed by a small Turkish
morphology generator. This sentence is both shown on screen and used as the
search query. If the object confidence is below the threshold, the keywords
are not trusted either: the query is just the object name and only the
definition block is shown. For vehicles the usage word is left out of the
intent, because compounds like "travel airplanes" are not natural.

When the user types plain text, the query is the object name combined with the
text. When text is written together with an image, the intent is also built
from that text and the blocks are only definition and answer, because the user
has said what they want.

## 6. Web search and paragraph selection

For Wikipedia, the page is first requested by its exact title, and if it is
not found a search is run. Disambiguation pages and pages that do not mention
the object are skipped. If the introduction is a single sentence, the
following paragraphs are added until it is long enough. The page's own
sections are read with the same request and feed the information blocks.

In search engine results, social media, marketplace, dictionary and
translation sites are filtered out, and one page is taken per domain. Results
are ranked by title. Titles with words that promise information move up,
titles with sales language move down. If the service returns a temporary
error, the query is retried once after a short wait.

The main text of the pages is extracted and split into paragraphs. A paragraph
must be between one hundred fifty and nine hundred characters, end with a
period, contain Turkish conjunctions, mention the object and carry no site
leftovers. Boilerplate sentences on recipe and Q&A sites that carry no
information are trimmed from the paragraph. Candidates are ranked by tf-idf
cosine similarity to a query built from the object name and the keywords. Term
frequency is the count of a stem in the paragraph divided by the total number
of stems in the paragraph. Inverse document frequency is the natural logarithm
of the number of candidates plus one, divided by the number of paragraphs that
contain the stem plus one, plus one. This calculation was written without a
ready-made library. To tolerate Turkish suffixes, the first five letters of a
word are used as its stem. One paragraph is taken per source, and duplicates
with high Jaccard similarity are removed.

## 7. Information blocks

The output is not a flat list of paragraphs but titled blocks based on the
object's family. Every turn starts with a definition block. If the search
intent differs from the object name, its own block comes next. Then come the
family-specific blocks: recipe and history for food, history and how to play
for instruments, characteristics and habitat for living things, history and
types for vehicles, varieties and uses for other products. The family is found
from the keywords with the family and domain roles. Domain words like aviation
or maritime point to the vehicle family. The schema lives in the block file in
the data folder.

Each block runs its own query, the queries are sent two at a time in parallel,
and all results are downloaded into a single pool. Each page carries the block
query it came from. A block looks at the pages of its own query first, and the
pool is a fallback. A block paragraph must contain at least two different
aspect stems and be similar to the aspect query above a certain threshold. If
no paragraph passes the threshold, the block is not shown. So each turn shows
the blocks the sources actually support, not a fixed number of blocks. The
thresholds were chosen by looking at the distribution of block scores over
twelve measured turns.

A recipe or variety list is structure, not a flat paragraph. The HTML
structure of the page is read with lxml, no language model is used. Bullet
lists, steps after a preparation heading, and subheadings with the first
sentence below them are extracted. Navigation, footer and comment areas are
dropped. Subheadings count as varieties only if they mention the object and
carry no sales language. The format field in the block schema says which
structure to look for. Structure is taken only from pages of the block's own
query and from pages whose title mentions the object. For structured blocks
the fill order is page structure, Wikipedia section, then plain paragraph. For
paragraph blocks the Wikipedia section is tried first.

The blocks are presented as one text with headings, numbered footnotes on
paragraphs and a source list at the end. In the measurement, the recipe block
for a hot dog gave a ten-item ingredient list and six preparation steps. For a
camera, the varieties block listed five camera types with short descriptions.

## 8. Chat context and memory

The session keeps the object, keywords and family of the last three turns.
When a new turn comes in, these turns are checked from newest to oldest, and
the first one that meets one of three conditions counts as the same topic: a
shared keyword, a shared word in the object names, or the same family. In the
default product family, the family alone is not enough and a shared word is
also required, otherwise a bag and a phone would count as the same topic. If
no turn matches, the topic has changed and old turns do not affect the search.

When a link is made, it has two effects. The previous object's name enters the
search intent only if the two names share their last word, in which case the
names are merged into one compound, like handbag and backpack. If the names
are unrelated, the intent does not change, because merging two unrelated names
into one query does not give meaningful results. A shared keyword gives
priority in paragraph ranking.

The link is visible in three places on screen. Words that came into the intent
sentence from the previous turn are highlighted. The top of the card shows the
link with the previous turn and the family, and anything that went into the
query. The chat line below the input field shows the turn count and the
consecutive objects that stayed in the same family, or says new topic if there
is no link. The turn counter is independent of the memory window.

Plain text input is linked to the last object, and the query is the object
name combined with the text. This way the user can ask about the same object
without giving an image.

The session also keeps the source URLs it has shown and how many times each
object has been discussed. When the same object comes again, the user is told,
the definition is not repeated, pages shown before are not downloaded and the
blocks are filled with new sources. If no new sources are left, the previous
sources are used again and the user is told that as well. In the measurement,
the same hot dog image brought three different sets of sources in three turns
in a row, and the third turn brought history content.

## 9. Interface

The terminal interface shows each turn as a single card. The card opens right
after the input and fills in gradually. The object name, confidence, keywords
and search intent appear within half a second, the Wikipedia definition is
added a second or two later, and the remaining blocks arrive when the search
is done. Meanwhile a one-line progress indicator below the card says which
step is running. The card body is produced as markdown, and the same text is
printed in plain mode and written to the record file. With debug on, there is
a collapsible details section below the card that lists the candidates, the
queries and the block decisions. The sources, the duration and the record
number are on the bottom line of the card. Words that came into the intent
sentence from the previous turn are highlighted, the top of the card shows the
link with the previous turn and the family, and the chat line below the input
field sums up the turn count and the consecutive objects in the same family.

## 10. Record

Each turn is written to the record file under a session block. The input,
object and confidence, the classifier's opinion, the agreement decision, the
keywords, the context, the search intent, the search trace, the titled
information blocks with the source of each paragraph, and the status of the
turn are saved. The file is first written to a temporary file and then moved
atomically.

## 11. Library choices

Search uses ddgs. Official search services need a key and an account, which
conflicts with the goal of running with a single command. The other libraries
that work without a key run into bot protection and break unpredictably.
Temporary errors from the service are handled with one retry and the Wikipedia
fallback.

Trafilatura is used to extract the page body. It gives the most accurate
result for removing navigation and ads and is actively maintained. Paragraph
selection, the similarity calculation and structure extraction after that are
my own code.

No language model is used to produce the answers. The aim is for the answers
to come from web page content. A hosted model would break single-command use
with a key dependency, and a local model would bloat the project and shift the
weight of the work from the retrieval pipeline to the model's writing skills.

A plain JSON file was chosen for the records instead of a database. It needs
no setup, runs with a single command, can be read by a person, and uses the
same schema as the data source for keeping the context.

## 12. Limitations

In cluttered scenes the classification stays uncertain, and a low confidence
message is shown. The theme map is a closed list, so in a domain it does not
cover the keywords can stay generic. The search service limits requests under
heavy use, in which case the remaining queries and Wikipedia carry on.
Structured extraction depends on page structure, and on non-standard pages it
falls back to a plain paragraph. On product photos with a white background the
object list can be wrong on fine distinctions, and the agreement rule and the
classifier can only fix this if the right answer is in the candidate list. The
classifier knows 57 objects and has no opinion on the rest. There is no text
generation: paragraphs are taken from the source as they are, so there are no
smooth transitions between blocks.

