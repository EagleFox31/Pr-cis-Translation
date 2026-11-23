# Changelog

Toutes les évolutions notables de **Précis Translator**. Format
[Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versionnage
[SemVer](https://semver.org/lang/fr/). Le numéro ci-dessous est la **version
projet** (le tag git) ; les composants — backend, moteurs, interface — portent
leurs propres numéros internes.

Rubriques : `Ajouté`, `Modifié`, `Corrigé`, `Retiré`, `Sécurité`.

## [1.11.0](https://github.com/EagleFox31/Pr-cis-Translation/compare/v1.10.0...v1.11.0) (2026-11-21)


### Features

* **beta:** invitation mail, resend and simplified admin beta screen ([#97](https://github.com/EagleFox31/Pr-cis-Translation/issues/97)) ([b9d21cb](https://github.com/EagleFox31/Pr-cis-Translation/commit/b9d21cbb468ac7eab7849612fb31d26925089ee2))
* **images:** offer image translation after the text, severity-based admin emails and admin preview fixes ([#96](https://github.com/EagleFox31/Pr-cis-Translation/issues/96)) ([05df336](https://github.com/EagleFox31/Pr-cis-Translation/commit/05df3360f21bae5fadcfc045687397c4b3a6a21c))

## [1.10.0](https://github.com/EagleFox31/Pr-cis-Translation/compare/v1.9.0...v1.10.0) (2026-11-18)


### Features

* **release:** annonce WhatsApp automatique après déploiement ([#88](https://github.com/EagleFox31/Pr-cis-Translation/issues/88)) ([ee5aa87](https://github.com/EagleFox31/Pr-cis-Translation/commit/ee5aa878f04a08e7a72bb8e6cd871968277527b1))


### Bug Fixes

* **legal:** name OVHcloud as host instead of AWS ([#92](https://github.com/EagleFox31/Pr-cis-Translation/issues/92)) ([9a55198](https://github.com/EagleFox31/Pr-cis-Translation/commit/9a55198d407d43a0f51dc32d643ac96159b995dd))
* **nouveautes:** let tooling-only and same-day releases pass the catalogue guard ([#93](https://github.com/EagleFox31/Pr-cis-Translation/issues/93)) ([3c94e3d](https://github.com/EagleFox31/Pr-cis-Translation/commit/3c94e3d6f1e56fdc1eeeca1b329ee4b43ac43f95))
* **nouveautes:** publish 1.8.0 and 1.9.0 features in the catalogue ([#91](https://github.com/EagleFox31/Pr-cis-Translation/issues/91)) ([b04c0d4](https://github.com/EagleFox31/Pr-cis-Translation/commit/b04c0d49e17865a1b8ced7fc9d8ee3bea3fc3443))

## [1.9.0](https://github.com/EagleFox31/Pr-cis-Translation/compare/v1.8.0...v1.9.0) (2026-11-18)


### Features

* customer feedback — admin preview, pricing, account panel, home credibility, sub-menu ([#83](https://github.com/EagleFox31/Pr-cis-Translation/issues/83)) ([8b80d03](https://github.com/EagleFox31/Pr-cis-Translation/commit/8b80d03bee29d33be963c04b275a0ddef86c0284))
* **translate:** free translation mode with preview of unpaid pages ([#85](https://github.com/EagleFox31/Pr-cis-Translation/issues/85), [#86](https://github.com/EagleFox31/Pr-cis-Translation/issues/86)) ([2e58586](https://github.com/EagleFox31/Pr-cis-Translation/commit/2e58586ccfa8eb20778ee6c6211b0aaae2a92f3a))


### Bug Fixes

* **deploy:** refuse VPS deploy on low disk, stop false rollback alarm ([#80](https://github.com/EagleFox31/Pr-cis-Translation/issues/80)) ([bbcd8e7](https://github.com/EagleFox31/Pr-cis-Translation/commit/bbcd8e7275a4558afb529d3998a70e2cf287e386))
* **email:** retry transient SMTP failures and surface failed alerts ([#82](https://github.com/EagleFox31/Pr-cis-Translation/issues/82)) ([69f9745](https://github.com/EagleFox31/Pr-cis-Translation/commit/69f97459ef464acc66e7142f57557b9a3a79872b))
* **frontend:** build the extension ZIP into the image so /extension/precis-extension.zip is served in production ([#84](https://github.com/EagleFox31/Pr-cis-Translation/issues/84)) ([27e945c](https://github.com/EagleFox31/Pr-cis-Translation/commit/27e945c082536e78b6ae14ca8f195e5c64bc8906))
* **invitations:** allow resending an invitation with per-sender and per-address caps ([#81](https://github.com/EagleFox31/Pr-cis-Translation/issues/81)) ([4f1a4a2](https://github.com/EagleFox31/Pr-cis-Translation/commit/4f1a4a26dbfda877faa77dcb5a395d52d31df2c3))

## [1.8.0](https://github.com/EagleFox31/Pr-cis-Translation/compare/v1.7.0...v1.8.0) (2026-11-15)


### Features

* **auth:** extension sign-in through the website with one-time code and PKCE ([d3b4c69](https://github.com/EagleFox31/Pr-cis-Translation/commit/d3b4c69214774c644c4f7579f8cadb1f5588c4dd))
* document image translation, PDF engine and viewer upgrades, extension usage tracking ([eac8aba](https://github.com/EagleFox31/Pr-cis-Translation/commit/eac8aba0d64dff9ce366b28963a4df53ad4ac422))
* **documents:** keep free-plan documents listed, lock access after 30 days ([1aa584e](https://github.com/EagleFox31/Pr-cis-Translation/commit/1aa584ef4f26334aac88caa2df2827e46370d7a7))
* **documents:** lighter selection mode and self-dismissing archive note ([962cb1e](https://github.com/EagleFox31/Pr-cis-Translation/commit/962cb1ec3b36d4837ab89194c8c49b99fdd4d0db))
* **documents:** multi-select delete, floating archive note, scroll chaining on extension page ([e507aa6](https://github.com/EagleFox31/Pr-cis-Translation/commit/e507aa6664fbd8d5cae84341e5383fbe44d243cd))
* **extension-page:** merge hero and browser choice into one compact card ([6ea558a](https://github.com/EagleFox31/Pr-cis-Translation/commit/6ea558a4ace6211cb465d16cb6a65547b139b74b))
* **extension:** sign in with the website instead of a password form ([a8e2c0a](https://github.com/EagleFox31/Pr-cis-Translation/commit/a8e2c0a64baac4adb73f19984ac66d710e942131))
* **home:** floating back-to-top button; fix(extension): no empty install tab on phones, tabs fit the width ([e1fa21e](https://github.com/EagleFox31/Pr-cis-Translation/commit/e1fa21e6b1b990ac42433dd312999b521f618f9f))
* **navigation:** floating Home button on every page except home; align floating button with the content frame ([30850b2](https://github.com/EagleFox31/Pr-cis-Translation/commit/30850b2b892192e19163a72878ac4cacc69b08e6))
* **navigation:** group page links apart, drop Nouveautes from the menu, fade between pages ([0a148c8](https://github.com/EagleFox31/Pr-cis-Translation/commit/0a148c8f8e526e9c79703bb919a89cf71d0a3d7e))
* **navigation:** same top bar on every page with a second row for multi-page sections ([9dfec77](https://github.com/EagleFox31/Pr-cis-Translation/commit/9dfec77f756ad9b61911237e90150e6b8510b0f6))
* Nouveautés (what's new tour, catalogue, e-mail announcements) and shared navigation ([dfe86e5](https://github.com/EagleFox31/Pr-cis-Translation/commit/dfe86e55519ffe2ac61e39d61d47f2a4611e0a28))
* **nouveautes:** account panel row with unseen-count badge and email switch ([ab709f4](https://github.com/EagleFox31/Pr-cis-Translation/commit/ab709f46f2a26fe9619dd342d35fa0090f9b6220))
* **nouveautes:** admin-only catalogue entries shown to administrators only ([8551b93](https://github.com/EagleFox31/Pr-cis-Translation/commit/8551b935deb4351a26f4ccb9a47453d7a43c1a89))
* **nouveautes:** bilingual feature catalogue with validation tests ([13afa19](https://github.com/EagleFox31/Pr-cis-Translation/commit/13afa191807c703a6c787c68c0056bf72d8bf2a6))
* **nouveautes:** end screen offering release emails after the welcome tour ([5bf51af](https://github.com/EagleFox31/Pr-cis-Translation/commit/5bf51af29206de57b97937a3fee4245af9c85e50))
* **nouveautes:** five-slide welcome tour and since-last-visit window ([6e7ca0c](https://github.com/EagleFox31/Pr-cis-Translation/commit/6e7ca0c65577d1423c769e1fb8662ebf08fe348a))
* **nouveautes:** language switch kept usable during the welcome tour ([3f566eb](https://github.com/EagleFox31/Pr-cis-Translation/commit/3f566ebcae69f29986a1b23e57426224dcc3100b))
* **nouveautes:** news API with unseen items, subscription and signed one-click unsubscribe ([54c9887](https://github.com/EagleFox31/Pr-cis-Translation/commit/54c9887ab5cb3bc7fdd6a2d6f8da9b40c7816c77))
* **nouveautes:** public features page and one-click unsubscribe page ([c824ab6](https://github.com/EagleFox31/Pr-cis-Translation/commit/c824ab62b53ac790867ff4dc013266be52c38e6f))
* **nouveautes:** redesigned account panel with archived documents ([e59cebc](https://github.com/EagleFox31/Pr-cis-Translation/commit/e59cebce80a7e7f40fa5499f77840323d68fcbea))
* **nouveautes:** release email with one-click unsubscribe and resumable batched sending ([6c525cf](https://github.com/EagleFox31/Pr-cis-Translation/commit/6c525cf5b022da95d14d7cbf8b059b0f0b5efe84))
* **nouveautes:** user news fields and send register (migration 0024) ([2b56e13](https://github.com/EagleFox31/Pr-cis-Translation/commit/2b56e13b5384c7edfd292aed2be808eb3d9fd0a6))
* **ocr-image:** syllable hyphenation, figure-wide sibling sizing, optical centring and numbered dash bullets ([0ff9fac](https://github.com/EagleFox31/Pr-cis-Translation/commit/0ff9fac23513ce2b819018113fb7e913cb7d950b))
* **pdf:** rebuild drawn initials as styled text and keep ornate overlays above anchored text ([2d47bdf](https://github.com/EagleFox31/Pr-cis-Translation/commit/2d47bdf5d577aecda904cd8d1708563f1b05f9f5))
* **pricing:** beta and pay-per-page strips side by side under the plan grid ([7e1bf06](https://github.com/EagleFox31/Pr-cis-Translation/commit/7e1bf068b8f9573678b5f74997091e1c43247360))
* **site:** extension authorization and confirmation pages ([98c1bd8](https://github.com/EagleFox31/Pr-cis-Translation/commit/98c1bd8e97320b499ab714df7b497cbbc83534f9))
* **site:** full-height navy About section with owl seal, pledges and inline contact row ([a5b12e3](https://github.com/EagleFox31/Pr-cis-Translation/commit/a5b12e3edd98e594dc4da2a119c72a0e08d95b5c))
* **site:** full-width mobile menu rows with icons and a language block ([4c860c6](https://github.com/EagleFox31/Pr-cis-Translation/commit/4c860c60a79959a3462760ac56cee61451631466))
* **site:** integration pages share the admin top bar ([5e20aa2](https://github.com/EagleFox31/Pr-cis-Translation/commit/5e20aa272200a1010bc7330bf04e542078c76416))
* **site:** structured pricing and API panels with a fixed links footer ([595c2f4](https://github.com/EagleFox31/Pr-cis-Translation/commit/595c2f474664ef6e5bbdf20d20a400c8027af2d8))
* **viewer:** fit-to-page/width modes, page number field and comparison curtain ([50273a8](https://github.com/EagleFox31/Pr-cis-Translation/commit/50273a8787e9a8347a293d021de7a2517c56b66c))


### Bug Fixes

* **ci:** serve prerendered /extension page, portable test font and sender address in email test ([ee62b6c](https://github.com/EagleFox31/Pr-cis-Translation/commit/ee62b6c573c3ba60b743f0cf02661d6be8d24f59))
* **documents:** download names with non-Latin-1 characters no longer fail ([727018b](https://github.com/EagleFox31/Pr-cis-Translation/commit/727018b651270afe1b37840c262f6bb31b7d6f66))
* **hero:** align proof list with the action column on mobile ([66a1c1d](https://github.com/EagleFox31/Pr-cis-Translation/commit/66a1c1d25181b002c6c6b8df65488d0fc63fb7cd))
* **images:** erase letter halos, size sibling labels by ink height and center text in closed cells ([7499f4c](https://github.com/EagleFox31/Pr-cis-Translation/commit/7499f4c68f567d21c8cbf912b45625e4f97513c4))
* **images:** keep staggered figure labels in separate blocks ([57263ca](https://github.com/EagleFox31/Pr-cis-Translation/commit/57263ca4d24dd2359579a0f89da1081b6fd615fe))
* **legal:** use the shared top bar with its exit button instead of an in-page Back ([3429994](https://github.com/EagleFox31/Pr-cis-Translation/commit/3429994b5f1ab0a8bbeb70ed263ce51268f40a4d))
* **nouveautes:** never show the welcome tour twice ([ca95db1](https://github.com/EagleFox31/Pr-cis-Translation/commit/ca95db166c8a44a20a5e603429b597ac506090e3))
* **ocr-image:** centre labels optically in closed boxes and follow a band past the open-side limit ([f9eba5a](https://github.com/EagleFox31/Pr-cis-Translation/commit/f9eba5a04546d1ab53994b85375c49be5857257e))
* **ocr-image:** join stacked centred lines of a table cell and keep line count when siblings shrink ([ef414bf](https://github.com/EagleFox31/Pr-cis-Translation/commit/ef414bfa10dda63ade453128db526d4660621843))
* **ocr-image:** keep 2-px anti-aliased table rules out of the erase mask ([a886a73](https://github.com/EagleFox31/Pr-cis-Translation/commit/a886a73fc818876d0c044fd4bc8ca2136ecb32a3))
* **ocr-image:** raise the tolerated body reduction to 10 % before adding a line ([ba0eeb7](https://github.com/EagleFox31/Pr-cis-Translation/commit/ba0eeb70170401c3017eb00ceb1316f26ee7730f))
* **ocr-image:** shrink up to 5 % to keep the original line count before adding a line ([c388d73](https://github.com/EagleFox31/Pr-cis-Translation/commit/c388d73a5d52851d243beb7b83b3a380dc95fd7c))
* **pdf:** center text on its own frame and size drawn initials like the drawing ([160f79b](https://github.com/EagleFox31/Pr-cis-Translation/commit/160f79bd4b2a84bf1c5c391d5937160c96bc7a5e))
* **pdf:** hide glyphs masked by a later filled shape and split labels sitting in two distinct frames ([e51874a](https://github.com/EagleFox31/Pr-cis-Translation/commit/e51874aad9f7ee1c5ab82d4abff13a8d2abbcb6d))
* **pricing:** keep the original pay-per-page banner when the beta is closed ([4929199](https://github.com/EagleFox31/Pr-cis-Translation/commit/492919928e205fcd76e78a52a9fae9b9d7089202))
* **site:** compact FR/EN pill in the mobile menu ([66ba2d3](https://github.com/EagleFox31/Pr-cis-Translation/commit/66ba2d39405a270e36beaa6b4a1c0a434dc9baa4))
* **site:** fixed-height extension menu and panel with inner scrolling ([c47084d](https://github.com/EagleFox31/Pr-cis-Translation/commit/c47084d787418798c649859fcce42bec8ad2a46d))
* **site:** flat form card and compact About section on small screens ([9c41b73](https://github.com/EagleFox31/Pr-cis-Translation/commit/9c41b7351732a704a4159d5de51981ab6f4d42e1))
* **site:** flat full-width translation form on mobile ([9cd6f62](https://github.com/EagleFox31/Pr-cis-Translation/commit/9cd6f626708f9c478965551933deb6150ffd3bb6))
* **site:** icons on the About section social links ([4314c5e](https://github.com/EagleFox31/Pr-cis-Translation/commit/4314c5eca85fdc5e44cb7a2a1ff5e680992aa394))
* **site:** move the language switch into the mobile menu ([54f1393](https://github.com/EagleFox31/Pr-cis-Translation/commit/54f13935da55b26fca6027475322e5df2a78099b))
* **site:** profile avatar opens the documents drawer on every page ([c26dfae](https://github.com/EagleFox31/Pr-cis-Translation/commit/c26dfae530f1b3bb65eafc33d9712cfba177eb68))
* **site:** resilient lazy chunks, buffered modal buses and cross-page preview requests ([308e8bb](https://github.com/EagleFox31/Pr-cis-Translation/commit/308e8bb52802da09ced656a5ffdcab8640da4807))
* **site:** touch targets, shared pricing request, active language and mobile menu closing ([d8c1786](https://github.com/EagleFox31/Pr-cis-Translation/commit/d8c178683ee4155d60544e97a7075e647689051d))
* **tests:** make nouveautes catalogue suite runnable as a plain script in CI ([e934bd6](https://github.com/EagleFox31/Pr-cis-Translation/commit/e934bd60b76f880a185ff2ced05bf959bbcca566))
* **viewer:** keep both zoomed pages reachable horizontally and make one wheel gesture do one action ([8521d22](https://github.com/EagleFox31/Pr-cis-Translation/commit/8521d226d5513a95c89cacea73a9066355cd0308))


### Performance Improvements

* **site:** drop unused Urbanist, JetBrains Mono and tabler-icons stylesheets ([0831fa4](https://github.com/EagleFox31/Pr-cis-Translation/commit/0831fa46aff2dbd87a39b13a3f90a44b65716ee6))
* **site:** fluidity and responsive pass ([8f264a8](https://github.com/EagleFox31/Pr-cis-Translation/commit/8f264a8e1eebfa5595521b591fdd6db149be3501))
* **site:** load secondary pages and modals on demand, shorten the splash ([f3193dd](https://github.com/EagleFox31/Pr-cis-Translation/commit/f3193dd980b89200ef02ba22fbe1ee66810fe36d))
* **site:** load the landing page chunk before first render and prefetch pages on link intent ([13cdea8](https://github.com/EagleFox31/Pr-cis-Translation/commit/13cdea8936cb1b53b592eb3f6fc6596e050baf7b))
* **site:** replace scroll timelines and load pdf.js on demand ([c41b49a](https://github.com/EagleFox31/Pr-cis-Translation/commit/c41b49ac1ad820019d152694c2658addaead503c))
* **site:** ship only the French dictionary in the main bundle ([602fb6f](https://github.com/EagleFox31/Pr-cis-Translation/commit/602fb6f4bf6f71c73ca4c098d29cff1e1d45f452))

## [1.7.0](https://github.com/EagleFox31/Pr-cis-Translation/compare/v1.6.2...v1.7.0) (2026-11-09)


### Features

* **extension:** distribution, install page and per-page limits ([#55](https://github.com/EagleFox31/Pr-cis-Translation/issues/55)) ([3bfbdc2](https://github.com/EagleFox31/Pr-cis-Translation/commit/3bfbdc2f2277a91d04738af37fb86b323c7f1e57))
* **invitations:** invite relatives to use Précis ([#32](https://github.com/EagleFox31/Pr-cis-Translation/issues/32)) ([3bfbdc2](https://github.com/EagleFox31/Pr-cis-Translation/commit/3bfbdc2f2277a91d04738af37fb86b323c7f1e57))
* **ocr:** page-by-page scan reading, unreadable pages and embedded objects translation ([#56](https://github.com/EagleFox31/Pr-cis-Translation/issues/56)) ([3bfbdc2](https://github.com/EagleFox31/Pr-cis-Translation/commit/3bfbdc2f2277a91d04738af37fb86b323c7f1e57))
* **pages:** beta, about, legal pages and credits source ([#54](https://github.com/EagleFox31/Pr-cis-Translation/issues/54)) ([3bfbdc2](https://github.com/EagleFox31/Pr-cis-Translation/commit/3bfbdc2f2277a91d04738af37fb86b323c7f1e57))
* **payments:** signed orchestrator event inbox ([#52](https://github.com/EagleFox31/Pr-cis-Translation/issues/52)) ([3bfbdc2](https://github.com/EagleFox31/Pr-cis-Translation/commit/3bfbdc2f2277a91d04738af37fb86b323c7f1e57))
* **pptx:** resume, pause and cancel; beta and anti-abuse; PPTX and preview fixes ([#53](https://github.com/EagleFox31/Pr-cis-Translation/issues/53)) ([3bfbdc2](https://github.com/EagleFox31/Pr-cis-Translation/commit/3bfbdc2f2277a91d04738af37fb86b323c7f1e57))
* **seo:** intent landing pages ([#59](https://github.com/EagleFox31/Pr-cis-Translation/issues/59)) ([3bfbdc2](https://github.com/EagleFox31/Pr-cis-Translation/commit/3bfbdc2f2277a91d04738af37fb86b323c7f1e57))
* **viewer:** navigation, wheel, thumbnails, original view; retranslation fidelity; admin documents ([#35](https://github.com/EagleFox31/Pr-cis-Translation/issues/35)) ([3bfbdc2](https://github.com/EagleFox31/Pr-cis-Translation/commit/3bfbdc2f2277a91d04738af37fb86b323c7f1e57))


### Bug Fixes

* **seo:** canonical, structured data, sitemap and crawler access fixes ([#58](https://github.com/EagleFox31/Pr-cis-Translation/issues/58)) ([3bfbdc2](https://github.com/EagleFox31/Pr-cis-Translation/commit/3bfbdc2f2277a91d04738af37fb86b323c7f1e57))

## [1.6.2](https://github.com/EagleFox31/Pr-cis-Translation/compare/v1.6.1...v1.6.2) (2026-10-21)


### Bug Fixes

* **pricing:** remove fee notes from plan cards ([#49](https://github.com/EagleFox31/Pr-cis-Translation/issues/49)) ([3c18341](https://github.com/EagleFox31/Pr-cis-Translation/commit/3c18341272bbff35bb389fe724aaf3a0f3117c7c))

## [1.6.1](https://github.com/EagleFox31/Pr-cis-Translation/compare/v1.6.0...v1.6.1) (2026-10-21)


### Bug Fixes

* **pricing:** make billing period controls accessible and reliable ([#47](https://github.com/EagleFox31/Pr-cis-Translation/issues/47)) ([46a6392](https://github.com/EagleFox31/Pr-cis-Translation/commit/46a63926bb5d1ab42cace19b414f3217f92037f7))

## [1.6.0](https://github.com/EagleFox31/Pr-cis-Translation/compare/v1.5.2...v1.6.0) (2026-10-21)


### Features

* **trial:** offer five usable document pages per month ([#45](https://github.com/EagleFox31/Pr-cis-Translation/issues/45)) ([04395f5](https://github.com/EagleFox31/Pr-cis-Translation/commit/04395f59f2bd1da5750c49aec1cc1369c43d2c63))

## [1.5.2](https://github.com/EagleFox31/Pr-cis-Translation/compare/v1.5.1...v1.5.2) (2026-10-20)


### Bug Fixes

* **beta:** prevent repeated trials and flag suspicious applications ([#43](https://github.com/EagleFox31/Pr-cis-Translation/issues/43)) ([79d3586](https://github.com/EagleFox31/Pr-cis-Translation/commit/79d35862578327261f524cba0acb4f49f82907a9))

## [1.5.1](https://github.com/EagleFox31/Pr-cis-Translation/compare/v1.5.0...v1.5.1) (2026-10-20)


### Bug Fixes

* **ui:** simplify the public beta offer card ([#41](https://github.com/EagleFox31/Pr-cis-Translation/issues/41)) ([292112e](https://github.com/EagleFox31/Pr-cis-Translation/commit/292112e74f5c1f48fc6b3bda03761f85b49248d2))

## [1.5.0](https://github.com/EagleFox31/Pr-cis-Translation/compare/v1.4.1...v1.5.0) (2026-10-20)


### Features

* **beta:** publish the program and review tester applications ([#39](https://github.com/EagleFox31/Pr-cis-Translation/issues/39)) ([1084b61](https://github.com/EagleFox31/Pr-cis-Translation/commit/1084b617a948c822a9a90b8e85ebec9320c0a926))

## [1.4.1](https://github.com/EagleFox31/Pr-cis-Translation/compare/v1.4.0...v1.4.1) (2026-10-20)


### Bug Fixes

* **beta:** serve direct activation links through nginx ([#37](https://github.com/EagleFox31/Pr-cis-Translation/issues/37)) ([f25dfc7](https://github.com/EagleFox31/Pr-cis-Translation/commit/f25dfc73460101583f28f75a58ebcc79bdeb1ce8))
* **ui:** acknowledge delivered documents without free-plan restriction ([#36](https://github.com/EagleFox31/Pr-cis-Translation/issues/36)) ([0b568ed](https://github.com/EagleFox31/Pr-cis-Translation/commit/0b568edd9f08146e582fd53b6a846444a910a005))

## [1.4.0](https://github.com/EagleFox31/Pr-cis-Translation/compare/v1.3.0...v1.4.0) (2026-10-20)


### Features

* **beta:** manage invited testers with per-format quotas ([#33](https://github.com/EagleFox31/Pr-cis-Translation/issues/33)) ([4c7f80e](https://github.com/EagleFox31/Pr-cis-Translation/commit/4c7f80eb4b6aeb7a3ddaaf4ef0d5c0513bc0871e))


### Bug Fixes

* **config:** preserve Fapshi settings in production env imports ([#31](https://github.com/EagleFox31/Pr-cis-Translation/issues/31)) ([a4db1f6](https://github.com/EagleFox31/Pr-cis-Translation/commit/a4db1f6efefe9b7d1cc96560e5b273949a68ccc8))

## [1.3.0](https://github.com/EagleFox31/Pr-cis-Translation/compare/v1.2.0...v1.3.0) (2026-10-20)


### Features

* **paiement:** Fapshi, achat des pages manquantes et frais client (backend 1.2.0) ([44c9b8f](https://github.com/EagleFox31/Pr-cis-Translation/commit/44c9b8fd0cd5fb2eba4b6863f0a54dc88344462d))

## 1.2.0 (2026-10-20)


### Features

* **pdf:** polices non embarquées et correctifs de rendu (moteur 1.0.12) ([b5eb58c](https://github.com/EagleFox31/Pr-cis-Translation/commit/b5eb58c3955bba6c2a62afb2317f7cd34e9fd27c))
* **pdf:** résoudre les polices non embarquées (identique, clone, la plus proche) ([5e62360](https://github.com/EagleFox31/Pr-cis-Translation/commit/5e62360f396857696c16bc3c18d94eadce5c63f5))


### Bug Fixes

* **ci:** propagate production and connect AppFactory release automation ([#27](https://github.com/EagleFox31/Pr-cis-Translation/issues/27)) ([e169d2f](https://github.com/EagleFox31/Pr-cis-Translation/commit/e169d2f46ac88d3576c09646c08146c7cdc8de53))
* **pdf:** lire et reproduire l'italique synthétique (police droite penchée par la matrice de texte) ([47eb4bd](https://github.com/EagleFox31/Pr-cis-Translation/commit/47eb4bd9ab7769b0d69a7ecd36e213c460d4a185))
* **pdf:** lire et reproduire le gras synthétique (police Regular peinte en mode 2) ([8d55814](https://github.com/EagleFox31/Pr-cis-Translation/commit/8d55814ce4aae9e4c94a55400a58f31d74e50d7c))
* **pdf:** ne pas souder une ligne en capitales et la ligne en casse mixte qui suit ([a143361](https://github.com/EagleFox31/Pr-cis-Translation/commit/a1433619c9dbb906d5b30b1ab5ac001b3dca16ce))
* **pdf:** polices — catégorie serif/sans respectée, noms composés, licences, absences bornées ([982b102](https://github.com/EagleFox31/Pr-cis-Translation/commit/982b1026613ed9ef760ef9565e91f5f7174581da))
* **pdf:** polices — liste blanche Google Fonts, rendu dégradé non mis en cache, polices système désactivées par défaut ([7782f45](https://github.com/EagleFox31/Pr-cis-Translation/commit/7782f45d1458cd25c3c1316192602a9aaf7bb8eb))
* **pdf:** rattacher chaque pose d'image à son objet et reporter son opacité ([185e577](https://github.com/EagleFox31/Pr-cis-Translation/commit/185e57730f07067e886f0f6cfd096993cb66b674))
* **release:** bound first AppFactory release to deployed lineage ([#28](https://github.com/EagleFox31/Pr-cis-Translation/issues/28)) ([1e93b19](https://github.com/EagleFox31/Pr-cis-Translation/commit/1e93b19766b9ab53fbd981b3208fcdd63264bac4))
* **traduction:** même libellé, même traduction d'une page à l'autre ([d51b589](https://github.com/EagleFox31/Pr-cis-Translation/commit/d51b589cce3952e7768561da1401ffdc64dcffed))
* **traduction:** redemander un fragment rendu entièrement inchangé ([88b8a82](https://github.com/EagleFox31/Pr-cis-Translation/commit/88b8a82faa2054eeaa489147bd6dfd3f1c15c2a4))

## [Non publié]

### Ajouté
- Excel : gestion de l'expansion. Une traduction plus longue que sa source
  élargit sa colonne (selon l'alignement et les voisines vides) au lieu d'être
  coupée, une cellule à retour à la ligne gagne la hauteur de ses lignes en
  plus, un nombre dont le format porte un littéral traduit ne s'affiche plus
  en `#####`.
- **Paiement Fapshi** (Mobile Money MTN et Orange, Cameroun). Par défaut,
  paiement direct : le client saisit son numéro et valide l'invite reçue sur
  son téléphone ; le crédit arrive par le suivi du statut ou par le webhook
  (`FAPSHI_WEBHOOK_SECRET`). La page de paiement hébergée, affichée DANS la
  fenêtre de paiement sans défilement, est conservée en repli désactivé
  (`FAPSHI_FLOW=checkout`, voir `docs/deploiement.md`).
- **Crédits insuffisants à l'import** : au lieu d'un refus sec, la traduction
  propose d'acheter les pages manquantes ou de ne traduire que les pages
  couvertes (PDF, PPTX). Rien n'est lancé ni débité avant ce choix ; après
  l'achat, le document entier est traduit.
- **Achat à la page** : un seul champ (1 à 500 pages, 2 par défaut), montant
  recalculé à la volée ; bandeau dédié sous la grille des tarifs.
- PDF : polices non embarquées résolues (police identique locale ou Google
  Fonts sur liste blanche, sinon clone métrique, sinon la plus proche par
  largeurs mesurées) ; catalogue pré-chargé au build.

### Modifié
- Moteur XLSX `0.2.0` → `1.0.0`.
- Moteur PDF `1.0.5` → `1.0.12`.
- **Frais de transaction (3 %) à la charge du client**, affichés avant de
  payer : sous-total, frais, total. Le montant enregistré est le total payé ;
  les pages créditées ne changent pas.
- Forfait Gratuit : les pages achetées passent avant l'offre du mois et valent
  pour tous les formats (l'essai offert reste limité au PDF et au PPTX).
- Backend `1.1.0` → `1.2.0` : `/api/payments/quote` et `/plan/quote` renvoient
  `subtotal`, `fee`, `amount` ; `/api/pricing` expose `fee_percent` ; la
  traduction répond 402 `need_credits` (structuré) et accepte `covered_only`.

### Corrigé
- Un compte Gratuit qui a acheté des pages voit désormais la reconnaissance
  (OCR) d'un scan porter sur tout le document, et non sur la seule page d'essai.
- L'essai sur un scan propose de nouveau l'achat des pages manquantes : la
  limite d'OCR à une page ne réduit plus le document compté.
- Double dépense possible de crédits sur deux imports simultanés : le solde est
  relu sous verrou.
- PDF : gras et italique synthétiques lus et reproduits ; opacité des images
  reportée sur chaque pose ; une ligne en capitales n'est plus soudée à la
  ligne en casse mixte qui suit.
- Traduction : un même libellé reçoit la même traduction d'une page à
  l'autre ; un fragment rendu inchangé est redemandé au modèle.

## [1.1.0] - 2026-10-09 — Comptes, paiement et mise en ligne

### Ajouté
- **Traduction Excel complète, avec aperçu progressif** (moteur XLSX `0.2.0`).
  Les **dix** endroits où Excel range du texte sont désormais traités : chaînes
  partagées et en ligne, noms d'onglets, graphiques, zones de texte, les **deux**
  formats de commentaires (ancien et fils modernes), en-têtes de tableaux
  structurés, croisés dynamiques, formats de nombre personnalisés et propriétés
  du document. L'aperçu suit le même flux progressif que le PDF et le PPTX —
  socle en langue source affichable tout de suite, puis chaque feuille traduite
  greffée à sa place.
  Deux règles gouvernent le moteur : **on ne traduit jamais un nombre ni une
  formule** (une cellule cassée propage `#VALUE!` dans toute la feuille), et
  **on traduit la source, on aligne ses copies** — les caches de graphiques,
  d'en-têtes de tableaux et de croisés reflètent des cellules déjà traduites ;
  les retraduire donnerait deux formulations pour la même donnée.
  Ce qui n'est **pas** couvert : l'**expansion**. Une traduction plus longue que
  sa source déborde de sa colonne ou s'affiche en `#####`. C'est la raison du
  `0.2.0` plutôt qu'un `1.0.0`.
- **Journal central des erreurs** : toutes les erreurs (interface, backend, API)
  sont captées et regroupées par empreinte. Capture front (erreurs JS, promesses
  rejetées, rendu React via `ErrorBoundary`, échecs réseau/5xx) → `POST
  /api/logs/client` ; capture backend (handler d'exception global + tout
  `logger.error` via un handler DB). Vue d'administration **`/admin/logs`**
  (réservée aux comptes admin) : liste groupée, filtres, détail (pile + contexte),
  et cycle **exporter → marquer traité → supprimer** (suppression refusée tant
  qu'un log n'est pas traité). Alerte e-mail à l'admin au-delà d'un seuil de logs
  non traités (throttlée). Migration `0006_error_logs`.
- **Console d'administration des comptes** (`/admin/users`, réservée admin) :
  liste filtrable des comptes et changement de plan. Sert à promouvoir un testeur
  (Starter/Pro) sans desserrer le forfait Gratuit. Garde-fous : plan restreint à
  une liste blanche, et un admin ne peut pas changer son propre plan
  (anti-verrouillage).
- **Vitesse de traitement affichée sur les cartes de tarifs** : le gratuit passe
  en file standard, chaque palier payant remonte dans la file (priorité 0→3).
  C'est le nouveau levier de vente. ⚠ L'attribut est *déclaré et vendu* ; son
  application réelle (l'ordonnancement de la file) reste à faire — chantier
  « file de priorité ».

- **Assistance / support** : les utilisateurs connectés peuvent **signaler un
  problème** ou demander de l'**aide sur leur abonnement** depuis une fenêtre
  (catégorie + sujet + message ; la page d'origine et le plan partent avec la
  demande sans être saisis). Accessible depuis le tiroir de compte. Vue
  d'administration **`/admin/support`** (menu Administration) : liste filtrable,
  détail, cycle **traiter (note interne) → supprimer** (suppression refusée tant
  qu'un ticket est ouvert). Alerte e-mail à l'admin à chaque ticket. Migration
  `0007_support_tickets`. **Référencement automatique du document** : signaler
  un problème depuis l'aperçu (barre d'outils) ou une carte de bibliothèque
  attache l'identité du document (id + nom) au ticket — l'utilisateur ne saisit
  rien, l'admin voit tout de suite de quel document il s'agit.
- **File de priorité de traduction** : les traductions ne démarrent plus toutes
  en parallèle sans limite. Un ordonnanceur borné (`TRANSLATION_WORKERS`, défaut
  2) mène N traductions de front ; au-delà, les demandes attendent dans une file
  ordonnée par le **niveau de plan** (admin > pro > starter > gratuit), FIFO à
  priorité égale. C'est ce qui rend enfin RÉELLE la vitesse vendue sur la carte.
  Le client voit un état « en file d'attente » (événement SSE `queued`). Pas de
  préemption : un job prioritaire passe devant ceux qui attendent, sans couper un
  job en cours.

- **Paiement à la page depuis l'écran de traduction** : quand le forfait Gratuit
  n'a plus de crédit, le message d'erreur porte désormais un bouton **« Payer N
  page(s) »** qui ouvre directement le paiement mobile money du nombre exact de
  pages du document, puis **relance la traduction** une fois payé. Le 402 « crédits
  insuffisants » renvoie une réponse structurée (`pages_needed`) pour que le client
  sache quoi facturer sans que l'utilisateur ait à deviner.

### Modifié
- **Aperçu d'essai — projecteur à un seul canevas** : la fenêtre nette qui suit
  le curseur ne s'appuie plus sur un second canevas « net » qu'il fallait aligner
  au pixel (il se décalait au zoom, laissant une zone blanche). Un seul canevas
  désormais, assombri par un voile percé d'un trou — aucune couche à aligner,
  plus de décalage.
- **Filigrane d'essai = mini-publicité, cuite dans les pixels** : « PRÉCIS ·
  Professional Translation · <site> » (contenu configurable via `BRAND_NAME`,
  `BRAND_TAGLINE`, `PUBLIC_SITE`). Il n'est plus une couche de texte détachable
  mais fait partie de l'image (double rastérisation) — le retirer demande de
  retoucher l'image, pas de supprimer un objet texte.
- **Tarifs zone A (Cameroun, FCFA) baissés** pour l'adoption bêta : Starter
  2 500 → **1 500** F/mois (annuel 1 900 → 1 200), Pro 6 900 → **4 500** F/mois
  (annuel 5 200 → 3 500), page à l'unité 100 → **75** F. Zones B/C inchangées.

### Sécurité
- **Un secret qui s'annonce provisoire est désormais refusé en production.**
  `dev-secret-key-change-in-production-…` traversait les trois contrôles : absent
  de la liste noire, sans marqueur connu (la liste cherchait `change-me`, le
  secret disait `change-in-production`) et assez long pour passer le plancher. Il
  aurait signé les jetons en ligne, et quiconque ayant lu ce fichier aurait pu
  forger un jeton d'administrateur.
- **`FRONTEND_URL` resté sur `localhost` bloque le démarrage en production.**
  Ce n'est pas un secret, l'application démarrait très bien sans lui : les liens
  de vérification de compte et le retour de connexion Google partaient vers la
  machine de l'utilisateur — **aucune inscription ne pouvait aboutir**, sans une
  ligne de journal.

### Corrigé
- **Quatre lectures de fichier figeaient l'application entière.** Un
  `open().read()` dans un `async def` bloque la boucle d'événements : avec un
  seul worker uvicorn et des fichiers jusqu'à 100 Mo, un téléchargement
  suspendait les aperçus de tous les autres utilisateurs, flux SSE de la
  traduction progressive compris. Lectures déportées hors de la boucle
  (`run_in_threadpool` / `asyncio.to_thread`).
- **Les 23 dépendances du backend sont épinglées** (`==` au lieu de `>=`) aux
  versions sur lesquelles les 21 suites passent : une construction d'image ne
  ramène plus une version majeure non testée.
- Les sorties des bancs d'essai (`.ocr_out/`, plusieurs dizaines de Mo,
  régénérables) ne sont plus candidates au suivi de version.
- Décomptes de tests périmés corrigés dans six documents (13 suites / 313
  contrôles → **21 suites / 418 contrôles**).

### Ajouté (mise en ligne)
- [`docs/deploiement.md`](docs/deploiement.md) : la marche à suivre pour mettre
  le service en ligne sur une machine AWS derrière Cloudflare — choix de
  l'hébergement argumenté, configuration obligatoire, HTTPS, parcours de
  vérification, limites connues et retour arrière.

Limites connues (assumées, non bloquantes) : PDF scannés non traduits (aucun OCR,
étude dans [`docs/etude-ocr.md`](docs/etude-ocr.md)) ; une colonne PDF justifiée de
≤ 5 lignes peut rester mal recollée ; moteur XLSX à l'état de squelette (couverture
partielle) ; l'interface n'a aucun test de rendu automatisé (vérification manuelle).

## [1.0.0] - 2026-07-24 — MVP

Première version stable. L'application traduit un document **sans lui faire perdre
sa mise en forme** : le texte est relevé avec sa géométrie et ses styles, traduit,
puis réinjecté dans le document d'origine — jamais reconstruit.

### Ajouté
- **Moteurs de traduction fidèle** : PDF (moteur v2 *from scratch* — glyphes →
  spans → lignes → paragraphes, reflow borné, rendu depuis le seul JSON), PPTX,
  DOCX, et XLSX (squelette). Chaque moteur est indépendant de l'application
  (`api → services → engines → rien`).
- **Aperçu progressif page par page** : flux SSE ; le document d'origine s'affiche
  d'abord, puis chaque page traduite s'y substitue dès qu'elle est prête (un thread
  mène le cycle complet extraction → traduction → rendu par page).
- **Reprise et cache honnête** : un job interrompu reprend sans repayer ; la clé de
  cache de rendu inclut la version du moteur (plus de rendu périmé servi en silence).
- **Comptes & facturation** : authentification **sans mot de passe** (code e-mail)
  + Google OAuth ; forfaits `free` (1 page/mois) · `starter` · `pro` · `enterprise`
  · `admin` ; paiement **à la page** via Campay (droit acquis au document, pas au plan).
- **Interface** React 19 + Vite : dépôt de document, bibliothèque, aperçu côte à
  côte (original ↔ traduction), mise en page **responsive** à cadre commun,
  **scroll-snap** par section, **mode agrandi** de l'aperçu, raccourcis clavier et
  souris, décor multilingue animé du hero.
- **Documentation** : `ARCHITECTURE.md`, README backend/frontend, contexte par
  moteur (`backend/engines/*/CONTEXTE.md`), doc API autonome (`npm run docs:api`),
  ce `CHANGELOG.md` et un `CONTRIBUTING.md`.

### Sécurité
- CORS restreint aux origines déclarées (plus de `*` avec `allow_credentials`).
- Plafonds de débit sur les routes d'authentification ; `503` parlant en cas de
  panne SMTP.

### Vérifié
- Interface : `npm run build` + parité i18n (`scripts/check-i18n.mjs`).
- Backend : 21 suites de tests hors ligne (aucun appel réseau ni DeepSeek),
  chacune en `exit=0`.
