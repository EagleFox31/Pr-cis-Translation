# Monthly discovery allowance

Verified free accounts receive five equivalent pages per calendar month. PDF pages
and PowerPoint slides each consume one unit; Word, Excel and UTF-8 TXT consume
one unit per started block of 500 extracted words. Office formulas, numeric cells
and blank cells do not consume words. Unspaced CJK characters count individually.
Long unbroken strings are split into 50-character word equivalents to prevent
an arbitrarily large token being billed as one word.
The same unit definition applies to normal plans and purchased page credits, so a
large Office file cannot bypass quota by being counted as one file.

Admission reserves the free allowance first, then any purchased credits, under
the existing account row lock before queuing work. Over-budget files receive the
existing structured quote. Only PDF and PowerPoint support explicitly requested
partial translation; Office/TXT files must be covered in full. Invalid files and
unverified free accounts without purchased credits do not start a worker.

The existing immutable usage ledger retains consumption after document deletion.
Existing refund/rebill logic returns failed work once and reinstates usage when
an orphaned worker eventually completes. Calendar rollover renews only the monthly
allowance; purchased credits remain separate. Earlier free-offer records retain
their original consumption. No migration, automatic trial enrollment, recruitment
opening or payment collection is needed.

Free pages are preview-only: a document covered only by free pages stays
unpaid, so its preview is watermarked and it cannot be downloaded. A document
that also consumes bought pages, a paid-plan document and a beta document are
marked `paid` (downloadable). Beta documents (`reglages["beta"]`) keep the
watermarked preview with the promotional mention, even on a paid plan (see
`docs/etude-source-credits.md`). Old unpaid previews retain their lock. The
frontend reads the document right from the accepted-job response or the library
record; it does not infer it from being on a paid subscription. All ownership checks remain server-side.

The public pricing response includes monthly and annual charge totals computed
with the same integer fee rounding as payment quotes. Plan cards display monthly
prices without fee notes or explanatory footnotes; the payment modal retains
the fee breakdown and full charge total. A rounded monthly equivalent is marked as
approximate when the annual total cannot be divided exactly into twelve minor-unit
amounts. Pay-as-you-go remains the published base page rate plus the disclosed
fee; its total is confirmed by the existing payment quote before collection.

Beta allowances, duration, admissions and normal subscription base prices are
unchanged. The discovery allowance is per verified account; beta-specific mailbox,
network and browser admission controls retain their existing beta scope.
