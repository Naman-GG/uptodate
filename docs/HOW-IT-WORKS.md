<!-- The non-technical explanation. The submission writeup is the technical one. -->

# How it works, in plain terms

uptodate reads every job description the way a person would, works
out who each role is for, and shows you the ones you can
actually apply to along with relevance score with the reason written on the card.

### How it works, in plain terms (with current numbers)

**1. It collects postings from everywhere at once.** Every morning it pulls from
201 company career pages and an Indian job aggregator. That is about 14,500 jobs,
gathered without you opening a single tab.

**2. It throws away the obvious misses for free.** Anything titled "Senior",
"Staff", "Director", or clearly not an engineering job gets dropped by simple
rules before any AI is involved. That removes three quarters of the pile and
costs nothing.

**3. It reads what is left.** Each of the remaining ~3,700 descriptions goes to a
language model on AWS, which pulls out the facts that decide eligibility: how
much experience is required, which countries you can do the job from, whether
there is a work-authorisation restriction, what kind of role it really is.

**4. Ordinary code makes the decision.** Those facts are checked against your
criteria by plain conditional statements. If a posting needs three years
and you have none, it is out, and the card says exactly that.

**5. What survives gets ranked.** Only then does a second AI step compare each
remaining job to your background and write one line explaining the match.

### Why this solves the problem

The thing that makes job hunting exhausting is going on 10 platforms for searching and when you find a promising posting, get four
paragraphs in, and find "5+ years required" or "must be authorised to work in the
US". You have just spent 10 minutes learning you were never eligible.

That information is always in the description, and never in the filters, because
it is written in prose and phrased differently every time. Job boards can only
filter on titles and tags, so they cannot see it.

This reads the prose instead. Out of 14,547 postings it found **154** that were
genuinely open to a final-year student in India — and for the other 14,393, it
can tell you which sentence disqualified you. **1,296 were not technical roles at
all. 840 required US work authorisation.** Those are tabs you never have to open.

### What it does

**1) Reads job descriptions, not just titles.** "Software Engineering Intern, Apple
Ads machine learning" is recognised as an ML role, so it survives a filter set to
AI/ML only. A keyword filter on the title would throw it away.

**2) Explains every decision.** Each card carries a one line reason for the match and
what the role wants that you have not shown. Nothing is a black box.

**3) Fills itself in from your resume.** Upload a PDF and it reads it directly, no
form filling. Your skills, background, graduation year and target fields are
proposed for you to check and edit.

**4) Lets you change who it is looking for.** Adjust the criteria - role types,
fields, how much experience, which countries, whether to include jobs open to any
country and the next run reevaluates all 14,547 postings against the new
rules.

**5) Is a working board, not a list.** Search, filter by match strength, and drag
cards between *To review*, *Applied* and *Interviewing* as you go.

**6) Shows its working.** A counter at the top tracks the full funnel: how many were
scanned, how many were read, how many survived — so you can see what it did on
your behalf rather than trusting it.

**7) Keeps itself up-to-date.** It runs on a schedule every morning without being asked,
so new postings appear on the board by themselves.

**Most Important - it is honest about weak sources.** Some postings come from an aggregator that cuts
descriptions short. Those cards say so, rather than pretending the match is as
certain as the others.
