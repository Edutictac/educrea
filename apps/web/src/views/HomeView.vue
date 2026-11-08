<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import AppIcon from '../components/AppIcon.vue'
import { locale } from '../i18n'
import { landingMessages } from '../i18n/landing'
const copy = computed(() => landingMessages[locale.value])
const answer = ref<number | null>(null)
const resourceIcons = ['puzzle', 'palette', 'book-open']
const benefitIcons = ['lightbulb', 'shapes', 'history']
watch(locale, () => { answer.value = null })
</script>

<template>
  <div class="home">
    <nav class="home-nav container" aria-label="EduCrea">
      <a href="#posibilidades">{{ copy.nav[0] }}</a><a href="#como-funciona">{{ copy.nav[1] }}</a><a href="#preguntas">{{ copy.nav[2] }}</a>
      <RouterLink to="/projects">{{ copy.enter }} <AppIcon name="chevron-right" :size="16" /></RouterLink>
    </nav>
    <section class="hero container" aria-labelledby="home-title">
      <div class="hero-copy">
        <p class="eyebrow"><span></span>{{ copy.eyebrow }}</p>
        <h1 id="home-title">{{ copy.title }} <em>{{ copy.accent }}</em></h1>
        <p class="hero-lead">{{ copy.lead }}</p>
        <div class="hero-actions"><RouterLink class="cta" to="/projects?nuevo=1">{{ copy.start }} <AppIcon name="chevron-right" /></RouterLink><a class="text-link" href="#como-funciona">{{ copy.discover }}</a></div>
        <p class="hero-note">{{ copy.note }}</p>
      </div>
      <div class="hero-visual">
        <span class="orbit orbit-one" aria-hidden="true"></span><span class="orbit orbit-two" aria-hidden="true"></span><span class="spark" aria-hidden="true"><AppIcon name="sparkles" :size="38" /></span>
        <div class="demo-card">
          <div class="demo-top"><span class="dots" aria-hidden="true"><i></i><i></i><i></i></span><span>{{ copy.demoLabel }}</span><AppIcon name="leaf" :size="18" /></div>
          <div class="demo-content">
            <div class="plant-art" aria-hidden="true"><AppIcon name="sun" :size="28" /><AppIcon name="leaf" :size="60" /><span></span></div>
            <p class="demo-subject">{{ copy.subject }}</p><h2>{{ copy.demoTitle }}</h2>
            <fieldset><legend>{{ copy.question }}</legend>
              <button v-for="(option, index) in copy.answers" :key="index" type="button" class="demo-answer" :class="{ selected: answer === index, correct: answer === index && index === 0 }" :aria-pressed="answer === index" @click="answer = index">
                <span class="answer-letter">{{ ['A', 'B', 'C'][index] }}</span>{{ option }}<AppIcon v-if="answer === index && index === 0" name="check" :size="18" />
              </button>
            </fieldset>
            <div class="feedback" :class="{ success: answer === 0 }" aria-live="polite" aria-atomic="true">{{ answer === null ? copy.hint : answer === 0 ? copy.correct : copy.retry }}</div>
            <button v-if="answer !== null" type="button" class="demo-reset" @click="answer = null">{{ copy.reset }} <AppIcon name="refresh-cw" :size="14" /></button>
          </div>
        </div>
        <div class="floating-note"><span><AppIcon name="lightbulb" :size="24" /></span>{{ copy.floating }}</div>
      </div>
    </section>
    <div class="strip"><div class="container"><span class="stamp">{{ copy.stamp }}</span><span v-for="(item, index) in copy.strip" :key="item"><AppIcon :name="['pencil', 'shapes', 'check', 'graduation-cap'][index]!" :size="18" />{{ item }}</span></div></div>
    <section class="beta-note container" aria-labelledby="beta-note-title">
      <AppIcon name="circle-help" :size="24" />
      <div><h2 id="beta-note-title">{{ copy.betaNoteTitle }}</h2><p>{{ copy.betaNote }}</p></div>
    </section>
    <section id="posibilidades" class="section container" aria-labelledby="resources-title">
      <div class="section-heading"><p class="eyebrow">{{ copy.resourcesLabel }}</p><h2 id="resources-title">{{ copy.resourcesTitle }}</h2><p>{{ copy.resourcesLead }}</p></div>
      <div class="resource-grid"><article v-for="(item, index) in copy.resources" :key="index" class="resource-card" :class="`resource-${index}`">
        <span class="resource-icon"><AppIcon :name="resourceIcons[index]!" :size="30" /></span><p class="resource-tag">{{ item.tag }}</p><h3>{{ item.title }}</h3><p>{{ item.text }}</p>
        <RouterLink to="/projects?nuevo=1" class="resource-link" :aria-label="`${copy.start}: ${item.title}`"><AppIcon name="chevron-right" :size="22" /></RouterLink>
      </article></div>
    </section>
    <section id="como-funciona" class="how-section" aria-labelledby="how-title"><div class="container section">
      <div class="section-heading"><p class="eyebrow">{{ copy.howLabel }}</p><h2 id="how-title">{{ copy.howTitle }}</h2></div>
      <ol class="steps"><li v-for="(step, index) in copy.steps" :key="index"><span class="step-number">0{{ index + 1 }}</span><h3>{{ step.title }}</h3><p>{{ step.text }}</p></li></ol>
    </div></section>
    <section class="section container benefit-layout" aria-labelledby="benefit-title">
      <div><p class="eyebrow">{{ copy.benefitLabel }}</p><h2 id="benefit-title">{{ copy.benefitTitle }}</h2><p class="benefit-lead">{{ copy.benefitLead }}</p>
        <ul class="benefits"><li v-for="(item, index) in copy.benefits" :key="index"><AppIcon :name="benefitIcons[index]!" :size="23" /><div><h3>{{ item.title }}</h3><p>{{ item.text }}</p></div></li></ul>
      </div>
      <aside class="example-note"><AppIcon name="sparkles" :size="30" /><p class="eyebrow">{{ copy.exampleLabel }}</p><blockquote>{{ copy.example }}</blockquote><p>{{ copy.exampleFoot }}</p><span class="note-line" aria-hidden="true"></span></aside>
    </section>
    <section id="preguntas" class="faq-section container section" aria-labelledby="faq-title">
      <div><p class="eyebrow">{{ copy.faqLabel }}</p><h2 id="faq-title">{{ copy.faqTitle }}</h2></div>
      <div class="faq-list"><details v-for="item in copy.faqs" :key="item.q"><summary>{{ item.q }}<AppIcon name="plus" :size="20" /></summary><p>{{ item.a }}</p></details></div>
    </section>
    <section class="closing"><div class="container"><p class="eyebrow">{{ copy.endLabel }}</p><h2>{{ copy.endTitle }}</h2><p>{{ copy.endText }}</p><RouterLink class="cta" to="/projects?nuevo=1">{{ copy.start }}<AppIcon name="chevron-right" /></RouterLink></div></section>
  </div>
</template>

<style scoped>
.home { --ink: var(--c-ink); --muted: var(--c-muted); color: var(--ink); background: var(--c-bg); }
.container { width: min(100% - 5rem, 1180px); margin-inline: auto; }
.home h1, .home h2, .home h3 { color: var(--ink); }
.home h2 { font-size: clamp(2rem, 3.2vw, 2.9rem); font-weight: 500; letter-spacing: -.045em; line-height: 1.15; }
.home p { color: var(--muted); }
.home-nav { display: flex; align-items: center; gap: 2rem; padding-block: 1.2rem; border-bottom: 1px solid #e3e7e1; font-size: .83rem; }
.home-nav a { text-decoration: none; color: #465f60; }.home-nav a:last-child { display: inline-flex; align-items: center; gap: .3rem; margin-left: auto; font-weight: 700; color: var(--ink); }
.eyebrow { display: flex; align-items: center; gap: .6rem; font-size: .7rem; letter-spacing: .15em; font-weight: 750; color: var(--ink) !important; margin: 0 0 1.3rem; }.eyebrow > span { width: 7px; height: 7px; border-radius: 50%; background: #bd653e; }
.hero { display: grid; grid-template-columns: 1.1fr 1fr; gap: 4rem; align-items: center; padding-block: 5.2rem 6rem; }
.hero h1 { font-size: clamp(3.1rem, 5.5vw, 5rem); font-weight: 550; line-height: 1.06; letter-spacing: -.065em; margin: 0 0 1.6rem; }.hero h1 em { display: block; font-family: Georgia, 'Times New Roman', serif; font-weight: 400; color: #ae5837; letter-spacing: -.055em; }
.hero-lead { font-size: 1.08rem; line-height: 1.8; max-width: 490px; }.hero-actions { display: flex; align-items: center; gap: 1.4rem; flex-wrap: wrap; margin-top: 2rem; }
.home a.cta { display: inline-flex; align-items: center; justify-content: center; gap: 1rem; background: #194e50; color: #fff; padding: 1rem 1.4rem; border-radius: 7px; text-decoration: none; font-weight: 650; font-size: .9rem; box-shadow: 0 5px 12px #173f4314; transition: background .2s, transform .2s; }.home a.cta:hover { background: #103a3d; transform: translateY(-2px); }
.text-link { font-size: .85rem; color: var(--ink); text-decoration-thickness: 1px; text-underline-offset: 5px; }.hero-note { font-size: .72rem; margin-top: 1.1rem; }
.hero-visual { position: relative; padding: 1.6rem 0 4rem; min-width: 0; }.orbit { position: absolute; border-radius: 50%; pointer-events: none; }.orbit-one { width: 105%; aspect-ratio: 1; top: 1%; left: -3%; background: #e7ede4; }.orbit-two { width: 75%; aspect-ratio: 1; bottom: 0; right: -5%; border: 1px solid #cdd9c8; }.spark { position: absolute; right: -1rem; top: -.5rem; color: #b66a37; transform: rotate(12deg); }
.demo-card { position: relative; background: white; border: 1px solid #dce2da; border-radius: 13px; box-shadow: 0 22px 65px #183e4215; transform: rotate(-2deg); }.demo-top { display: flex; align-items: center; justify-content: space-between; gap: 1rem; border-bottom: 1px solid #edf0e9; padding: .8rem 1.1rem; font-size: .58rem; letter-spacing: .1em; font-weight: 650; color: #647975; }.dots { display: flex; gap: 4px; }.dots i { width: 6px; height: 6px; border-radius: 50%; background: #d2dcd4; }.dots i:first-child { background: #d4ac87; }.demo-content { padding: 1.3rem 1.8rem 1.2rem; }
.plant-art { position: relative; height: 90px; width: 120px; margin: 0 auto .5rem; color: #618268; }.plant-art > .icon:first-child { position: absolute; top: 0; right: 0; color: #c19744; }.plant-art > .icon:nth-child(2) { position: absolute; left: 25px; bottom: 14px; transform: rotate(-28deg); }.plant-art > span:last-child { position: absolute; bottom: 7px; width: 65px; height: 10px; background: #efe4d0; border-radius: 50%; left: 25px; }
.demo-subject { text-align: center; font-size: .65rem; margin-bottom: .5rem; }.demo-content h2 { font-family: Georgia, serif; font-size: 1.65rem; text-align: center; letter-spacing: -.04em; margin-bottom: 1.5rem; }.demo-content fieldset { border: 0; padding: 0; margin: 0; }.demo-content legend { font-size: .83rem; color: var(--ink); line-height: 1.5; padding: 0; margin-bottom: .7rem; }
.demo-answer { width: 100%; justify-content: flex-start; min-height: 44px; text-align: left; padding: .6rem .7rem; border: 1px solid #dfe5df; background: #fff; color: #385554; font-size: .73rem; font-weight: 450; gap: .65rem; margin-bottom: .5rem; border-radius: 6px; line-height: 1.4; }.demo-answer:hover:not(:disabled), .demo-answer.selected { background: #f6eee4; border-color: #b68c64; }.demo-answer.correct, .demo-answer.correct:hover { background: #edf5ec; border-color: #739975; }.answer-letter { display: grid; place-items: center; width: 22px; height: 22px; flex: none; background: #f1f4ee; border-radius: 4px; font-size: .65rem; font-weight: 650; }
.feedback { font-size: .7rem; line-height: 1.6; margin-top: .6rem; color: #6a7267; min-height: 2.2rem; }.feedback.success { color: #315d34; }.demo-reset { background: none; color: #285958; border: 0; padding: .2rem 0; min-height: 30px; font-size: .7rem; }.demo-reset:hover:not(:disabled) { background: #edf5ec; }
.floating-note { pointer-events: none; position: absolute; bottom: -.2rem; left: -2.5rem; display: flex; gap: .8rem; align-items: center; padding: .8rem 1.2rem .8rem .8rem; border: 1px solid #e3dac5; background: #fffdf5; font-family: Georgia, serif; font-style: italic; font-size: .95rem; border-radius: 8px; box-shadow: 0 8px 24px #3d392c0d; transform: rotate(3deg); }.floating-note > span { display: grid; place-items: center; background: #f5e7c2; color: #956b21; border-radius: 6px; height: 40px; width: 40px; }
.strip { border-block: 1px solid #e0e5db; background: #f0f2eb; }.strip .container { display: flex; gap: 2rem; align-items: center; justify-content: space-between; padding-block: 1.4rem; }.strip span { display: inline-flex; align-items: center; gap: .65rem; font-size: .78rem; }.strip .stamp { font-size: .59rem; font-weight: 700; letter-spacing: .12em; color: #647267; }
.home .beta-note { display: flex; align-items: flex-start; gap: 1rem; margin-top: 2.5rem; padding: 1.15rem 1.4rem; border: 1px solid #e3dac5; background: #fffdf5; border-radius: 10px; }
.home .beta-note > .icon { flex: none; color: #956b21; margin-top: .1rem; }
.home .beta-note h2 { font-size: .92rem; font-weight: 650; letter-spacing: 0; line-height: 1.4; margin: 0 0 .35rem; }
.home .beta-note p { font-size: .8rem; line-height: 1.7; margin: 0; max-width: 900px; }
.section { padding-block: 5.5rem; scroll-margin-top: 85px; }.section-heading { max-width: 650px; margin-bottom: 2.5rem; }.section-heading > p:last-child { line-height: 1.8; max-width: 590px; margin-top: 1rem; font-size: .95rem; }
.resource-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.2rem; }.resource-card { padding: 2rem 1.7rem; position: relative; border-radius: 10px; border: 1px solid #dde4dc; background: #edf2e9; min-width: 0; }.resource-1 { background: #f6efe5; border-color: #e8dfd0; }.resource-2 { background: #eaf0f2; border-color: #dce3e6; }.resource-icon { display: grid; place-items: center; width: 58px; height: 58px; border-radius: 50%; background: #ffffff9c; margin-bottom: 2rem; }.resource-tag { text-transform: uppercase; letter-spacing: .1em; font-size: .58rem; font-weight: 700; }.resource-card h3 { font-size: 1.3rem; letter-spacing: -.025em; margin: .7rem 0 1rem; font-weight: 550; }.resource-card > p:last-of-type { font-size: .85rem; line-height: 1.85; padding-bottom: 2.2rem; }.resource-link { display: grid; place-items: center; position: absolute; right: 1.5rem; bottom: 1.5rem; height: 36px; width: 36px; border: 1px solid #aab7ab; border-radius: 50%; color: var(--ink); }.resource-link:hover { background: #fff; }
.how-section { background: #fffefa; border-block: 1px solid #e7e8df; scroll-margin-top: 60px; }.how-section .section-heading { max-width: 700px; }.steps { list-style: none; padding: 0; margin: 3rem 0 0; display: grid; grid-template-columns: repeat(3, 1fr); gap: 3rem; }.step-number { display: block; font-family: Georgia, serif; font-size: 2.5rem; color: #ac623e; padding-bottom: 1.2rem; border-bottom: 1px solid #dddfd3; margin-bottom: 1.4rem; }.steps h3 { font-size: 1.08rem; font-weight: 600; }.steps p { font-size: .88rem; line-height: 1.85; }
.benefit-layout { display: grid; grid-template-columns: 1.2fr 1fr; align-items: center; gap: 6rem; }.benefit-lead { line-height: 1.8; font-size: .95rem; margin-top: 1.2rem; }.benefits { list-style: none; padding: 0; margin-top: 2rem; }.benefits li { display: flex; align-items: flex-start; gap: 1rem; margin-top: 1.7rem; }.benefits li > .icon { color: #7b8668; margin-top: .2rem; }.benefits h3 { margin: 0 0 .5rem; font-size: .94rem; line-height: 1.5; font-weight: 600; }.benefits p { font-size: .84rem; line-height: 1.8; }
.example-note { background: #f2e9d8; border: 1px solid #e3d8c3; padding: 2.8rem 2.3rem; transform: rotate(2deg); border-radius: 5px 35px 5px 5px; box-shadow: 0 15px 35px #49412d0a; }.example-note > .icon { color: #a9683f; margin-bottom: 2rem; }.example-note .eyebrow { font-size: .6rem; }.example-note blockquote { margin: 1.5rem 0; font-family: Georgia, serif; font-size: clamp(1.4rem, 2vw, 1.8rem); line-height: 1.55; letter-spacing: -.02em; }.example-note > p:last-of-type { font-size: .75rem; margin-top: 2rem; }.note-line { display: block; width: 60px; height: 3px; background: #b16d44; margin-top: 2rem; }
.faq-section { display: grid; grid-template-columns: .9fr 1.4fr; gap: 5rem; border-top: 1px solid #e0e5db; }.faq-list details { border-bottom: 1px solid #dce2d9; padding-block: .6rem; }.faq-list details:first-child { border-top: 1px solid #dce2d9; }.faq-list summary { list-style: none; display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding-block: 1rem; font-size: .88rem; font-weight: 600; color: var(--ink); }.faq-list summary::-webkit-details-marker { display: none; }.faq-list details[open] summary > .icon { transform: rotate(45deg); }.faq-list details > p { font-size: .86rem; line-height: 1.9; margin: 0 2rem 1.2rem 0; }
.closing { text-align: center; background: #173f43; padding-block: 4.7rem; }.closing .eyebrow { justify-content: center; color: #c8d7c9 !important; }.closing h2 { color: #fffdf4; max-width: 680px; margin: 0 auto 1.3rem; }.closing p { color: #d1dfd8; font-size: .92rem; }.closing a.cta { margin-top: 1.4rem; background: #efe4c9; color: #173f43; }.closing a.cta:hover { background: #fff5db; }
@media (max-width: 1000px) { .container { width: min(100% - 3rem, 1180px); }.hero { gap: 2.5rem; }.hero-actions { gap: 1rem; }.strip .container { gap: 1rem; }.strip .stamp { display: none; }.benefit-layout { gap: 3rem; }.faq-section { gap: 2.5rem; }.demo-content { padding-inline: 1.2rem; }.floating-note { left: -1rem; font-size: .85rem; }.home-nav { gap: 1.2rem; } }
@media (max-width: 720px) { .container { width: calc(100% - 2.5rem); }.home-nav { gap: 1.2rem; overflow-x: auto; font-size: .72rem; padding-block: 1rem; }.home-nav a { flex-shrink: 0; }.home-nav a:nth-child(3), .home-nav a:last-child { display: none; }.hero { grid-template-columns: 1fr; padding-block: 3rem 4rem; gap: 2.5rem; }.hero h1 { max-width: 580px; font-size: clamp(2.8rem, 10vw, 4rem); }.hero-lead { font-size: 1rem; }.hero-visual { width: min(92%, 430px); margin: 0 auto; }.hero-note { line-height: 1.7; }.hero-actions { gap: 1.3rem; }.strip .container { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem .7rem; }.strip span { font-size: .71rem; }.section { padding-block: 3.5rem; }.home .beta-note { margin-top: 2rem; padding: 1rem; }.resource-grid, .steps, .benefit-layout, .faq-section { grid-template-columns: 1fr; }.resource-grid { gap: 1rem; }.resource-card { padding: 1.6rem; }.resource-icon { margin-bottom: 1rem; }.resource-card h3 { font-size: 1.25rem; }.resource-card > p:last-of-type { padding-bottom: 1rem; max-width: 500px; }.steps { gap: 1.8rem; }.step-number { padding-bottom: .6rem; margin-bottom: 1rem; }.benefit-layout { gap: 2rem; }.example-note { margin-inline: .5rem; padding: 2rem; }.faq-section { gap: 1.5rem; }.closing { padding-block: 3.5rem; }.spark { right: -.7rem; }.floating-note { left: -.8rem; padding-right: .8rem; }.hero-visual .orbit-two { right: 0; } }
@media (prefers-reduced-motion: reduce) { .home a.cta { transition: none; transform: none; } }
</style>
