"""
Calibration paragraphs — phonetically balanced for voice/EQ analysis.

Ragchew: The Rainbow Passage (Fairbanks 1960) — the gold standard for voice
analysis in telecommunications and speech pathology. Contains all English
phonemes in natural proportion and has been used in ITU/Bell Labs studies.

Contest: Phonetically dense contest operating text. Uses all NATO phonetic
alphabet words, digits zero through nine, contest exchanges, and the punchy
staccato rhythm of actual contest operating. Includes {callsign} substitution.

Both passages read aloud at natural pace take approximately 30–35 seconds.
"""

RAGCHEW_PARAGRAPH = """\
When the sunlight strikes raindrops in the air, they act as a prism and form \
a rainbow. The rainbow is a division of white light into many beautiful colors. \
These take the shape of a long round arch, with its path high above, and its \
two ends apparently beyond the horizon. There is, according to legend, a pot \
of gold at one end. People look, but no one ever finds it. When a man looks \
for something beyond his reach, his friends say he is looking for the pot of \
gold at the end of the rainbow. Throughout the centuries, people have explained \
the rainbow in various ways. Some have accepted it as a miracle without \
physical explanation. To the Hebrews it was a token that there would be no \
more universal floods. The Greeks used to imagine that it was a sign from the \
gods to foretell war or heavy rain."""

CONTEST_PARAGRAPH = RAGCHEW_PARAGRAPH
