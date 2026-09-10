'use strict';
(() => {
  const trigger = document.getElementById('newProject');
  if (!trigger) return;
  const dialog = document.createElement('dialog');
  dialog.id = 'createProjectDialog';
  dialog.className = 'project-wizard';
  dialog.setAttribute('aria-labelledby', 'wizardTitle');
  dialog.innerHTML = `
    <form id="createProjectForm" novalidate>
      <header class="wizard-heading"><p class="eyebrow">NEUES PROJEKT</p><h2 id="wizardTitle">Neues Projekt anlegen</h2><p>Zeitraum, Team und Schichten in drei Schritten einrichten. Alle Angaben bleiben anschließend bearbeitbar.</p></header>
      <ol class="wizard-steps" aria-label="Einrichtung"><li>1 · Zeitraum</li><li>2 · Team</li><li>3 · Schichten & Regeln</li></ol>
      <p id="wizardError" class="wizard-error" role="alert" hidden></p>
      <section class="wizard-step" data-step="0" aria-labelledby="wizardBasicsTitle">
        <h3 id="wizardBasicsTitle" tabindex="-1">Projekt benennen</h3>
        <label class="wizard-field">Projektname<input id="wizardName" required maxlength="120" autocomplete="off" placeholder="Zum Beispiel: Teamplanung Oktober"></label>
        <div class="wizard-grid"><label class="wizard-field">Von<input id="wizardStart" type="date" required></label><label class="wizard-field">Bis einschließlich<input id="wizardEnd" type="date" required></label></div>
        <label class="wizard-field">Zeitzone<input id="wizardTimezone" required maxlength="100" list="wizardTimezones" placeholder="Europe/Vienna"></label>
        <datalist id="wizardTimezones"><option value="Europe/Vienna"><option value="Europe/Berlin"><option value="Europe/Zurich"><option value="UTC"></datalist>
        <p class="muted">Die Schichtzeiten gelten in dieser Zeitzone. Ein Projekt kann bis zu 366 Tage umfassen.</p>
      </section>
      <section class="wizard-step" data-step="1" aria-labelledby="wizardTeamTitle" hidden>
        <h3 id="wizardTeamTitle" tabindex="-1">Wer gehört zum Team?</h3>
        <label class="wizard-field">Personen · ein Name pro Zeile<textarea id="wizardPeople" rows="6" required placeholder="Person A&#10;Person B&#10;Person C" aria-describedby="wizardPeopleHelp"></textarea></label>
        <p class="muted" id="wizardPeopleHelp">Optional pro Zeile: Name; Wochenstunden; Beschäftigung in %. Ohne Zusatz gelten die Werte unten. Wochenstunden sind die tatsächlich vereinbarten Stunden der Person; der Beschäftigungsgrad kürzt sie nicht nochmals.</p>
        <div class="wizard-grid"><label class="wizard-field">Wochenstunden als Vorgabe<input id="wizardWeeklyHours" type="number" min="0" max="168" step="0.25" value="40" required></label><label class="wizard-field">Beschäftigung in % als Vorgabe<input id="wizardEmploymentFraction" type="number" min="1" max="100" step="1" value="100" required></label></div>
        <p class="muted">Zielstunden = Wochenstunden × Kalendertage ÷ 7, ohne Feiertagsabzug. Individuelle Sollstunden, Abwesenheiten und Freigaben lassen sich anschließend in der Teammatrix anpassen.</p>
        <label class="wizard-field">Benötigte Funktionen · eine pro Zeile<textarea id="wizardPositions" rows="3" required placeholder="Funktion A&#10;Funktion B">Funktion A</textarea></label>
      </section>
      <section class="wizard-step" data-step="2" aria-labelledby="wizardShiftsTitle" hidden>
        <h3 id="wizardShiftsTitle" tabindex="-1">Welche Schichten werden besetzt?</h3>
        <p class="muted">Vorlagen wiederholen sich an den ausgewählten Wochentagen. Endet eine Schicht vor ihrem Beginn, läuft sie über Mitternacht. Die gesamte Dauer zählt als Arbeitszeit.</p>
        <div id="wizardTemplates"></div><button id="wizardAddTemplate" type="button" class="secondary">Schichtvorlage hinzufügen</button>
        <h3>Planungsregeln festlegen</h3><p class="muted">Die Startwerte sind bearbeitbare Vorgaben. Bitte die für das Team vereinbarten Regeln prüfen; die Einrichtung enthält keine rechtliche Prüfung.</p>
        <div class="wizard-grid">
          <label class="wizard-field">Mindestruhe · Stunden<input id="wizardMinRest" type="number" min="0" max="168" step="0.25" value="11" required></label>
          <label class="wizard-field">Ruhe nach Nachtschicht · Stunden<input id="wizardNightRest" type="number" min="0" max="168" step="0.25" value="11" required></label>
          <label class="wizard-field">Arbeitstage in Folge · höchstens<input id="wizardWorkDays" type="number" min="1" max="31" step="1" value="6" required></label>
          <label class="wizard-field">Nächte in Folge · höchstens<input id="wizardNights" type="number" min="1" max="31" step="1" value="3" required></label>
          <label class="wizard-field">Arbeitsstunden pro Tag · höchstens<input id="wizardDailyHours" type="number" min="0.25" max="25" step="0.25" value="12" required></label>
          <label class="wizard-field">Arbeitsstunden pro Kalenderwoche · höchstens<input id="wizardMaxWeeklyHours" type="number" min="0.25" max="175" step="0.25" value="48" required></label>
          <label class="wizard-field">Zusammenhängende Wochenruhe · Stunden<input id="wizardWeeklyRest" type="number" min="0" max="168" step="0.25" value="36" required></label>
        </div>
        <p class="muted">Wochenruhe wird je Kalenderwoche geprüft. 0 deaktiviert diese zusätzliche Vorgabe. Weitere Regeln stehen nach der Einrichtung unter „Regeln & Bedarf“ zur Verfügung.</p>
        <div id="wizardSummary" class="wizard-summary" aria-live="polite"></div>
        <label class="wizard-check"><input id="wizardRulesConfirmed" type="checkbox" required><span>Ich habe die gewählten Planungsregeln geprüft und bestätige sie für dieses Team.</span></label>
        <label class="wizard-check"><input id="wizardApprovalsConfirmed" type="checkbox"><span>Alle genannten Personen dürfen alle angelegten Funktionen ohne zusätzliche Qualifikationsnachweise ausführen. Ohne diese Bestätigung erteile ich die Freigaben später einzeln in der Teammatrix.</span></label>
        <label class="wizard-check"><input id="wizardContextConfirmed" type="checkbox"><span id="wizardContextLabel"></span></label>
        <p class="muted">Die Angaben zu Freigaben und Randzeiten sind freiwillig. Ohne vollständige Angaben bleibt das Projekt ein Entwurf und kann noch keinen vollständigen Plan liefern.</p>
      </section>
      <footer class="wizard-actions"><button id="wizardCancel" type="button" class="secondary">Abbrechen</button><button id="wizardBack" type="button" class="secondary" hidden>Zurück</button><button id="wizardNext" type="button" class="primary">Weiter</button><button id="wizardCreate" type="submit" class="primary" hidden>Projekt erstellen</button></footer>
    </form>`;
  document.body.append(dialog);
  const get = id => document.getElementById(id);
  const form = get('createProjectForm');
  const steps = Array.from(dialog.querySelectorAll('.wizard-step'));
  const weekdays = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];
  let step = 0, busy = false, fresh = true, templates = [], positionNames = [];
  const node = (tag, text, parent) => {
    const item = document.createElement(tag);
    if (text !== undefined) item.textContent = text;
    if (parent) parent.append(item);
    return item;
  };
  const dateValue = date => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  const utcDate = value => new Date(value + 'T00:00:00Z');
  const offsetDate = (value, amount) => {
    const date = utcDate(value);
    date.setUTCDate(date.getUTCDate() + amount);
    return date.toISOString().slice(0, 10);
  };
  const lines = value => value.split(/\r?\n/).map(row => row.trim()).filter(Boolean);
  const numeric = value => Number(String(value).trim().replace(',', '.'));
  const showError = message => {
    const error = get('wizardError');
    error.textContent = message;
    error.hidden = !message;
    if (message) error.scrollIntoView({block: 'nearest'});
  };
  function gotoStep(value) {
    step = value;
    steps.forEach((section, index) => { section.hidden = index !== step; });
    dialog.querySelectorAll('.wizard-steps li').forEach((item, index) => {
      if (index === step) item.setAttribute('aria-current', 'step');
      else item.removeAttribute('aria-current');
    });
    get('wizardBack').hidden = step === 0;
    get('wizardNext').hidden = step === 2;
    get('wizardCreate').hidden = step !== 2;
    showError('');
    steps[step].querySelector('h3').focus();
    if (step === 2) updateSummary();
  }
  function invalid(input, message) {
    input.setAttribute('aria-invalid', 'true');
    showError(message);
    input.focus();
    return false;
  }
  function validateInputs(section) {
    for (const input of section.querySelectorAll('input, textarea')) {
      input.removeAttribute('aria-invalid');
      if (!input.checkValidity()) {
        const label = input.closest('label')?.textContent.trim() || 'Angabe';
        return invalid(input, `${label}: ${input.validationMessage}`);
      }
    }
    return true;
  }
  function readPeople() {
    const rows = lines(get('wizardPeople').value);
    if (!rows.length || rows.length > 1000) throw Error('Bitte 1 bis 1000 Personen eintragen.');
    const seen = new Set();
    return rows.map((row, index) => {
      const parts = row.split(';').map(part => part.trim());
      const name = parts[0];
      const weekly = numeric(parts[1] || get('wizardWeeklyHours').value);
      const fraction = numeric(parts[2] || get('wizardEmploymentFraction').value);
      if (parts.length > 3 || !name || name.length > 120 || !Number.isFinite(weekly) || weekly < 0 || weekly > 168 || !Number.isInteger(fraction) || fraction < 1 || fraction > 100) {
        throw Error(`Person in Zeile ${index + 1}: Name; Wochenstunden (0–168); Beschäftigung in % (1–100) verwenden.`);
      }
      if (seen.has(name.toLocaleLowerCase())) throw Error(`Der Name „${name}“ kommt mehrfach vor. Bitte einen unterscheidbaren Zusatz angeben.`);
      seen.add(name.toLocaleLowerCase());
      return {name, weekly_hours: weekly, employment_fraction: fraction};
    });
  }
  function validateStep() {
    if (!validateInputs(steps[step])) return false;
    if (step === 0) {
      if (!get('wizardName').value.trim()) return invalid(get('wizardName'), 'Bitte einen Projektnamen eingeben.');
      const duration = (utcDate(get('wizardEnd').value) - utcDate(get('wizardStart').value)) / 86400000 + 1;
      if (!Number.isFinite(duration) || duration < 1 || duration > 366) return invalid(get('wizardEnd'), 'Der Planungszeitraum muss 1 bis 366 Tage umfassen.');
      try { new Intl.DateTimeFormat('de', {timeZone: get('wizardTimezone').value.trim()}).format(); }
      catch { return invalid(get('wizardTimezone'), 'Bitte eine gültige Zeitzone eingeben, zum Beispiel Europe/Vienna.'); }
    }
    if (step === 1) {
      try { readPeople(); } catch (error) { return invalid(get('wizardPeople'), error.message); }
      const names = lines(get('wizardPositions').value);
      if (!names.length || names.length > 100 || names.some(name => name.length > 120)) return invalid(get('wizardPositions'), 'Bitte 1 bis 100 Funktionen mit höchstens 120 Zeichen pro Name eintragen.');
      if (new Set(names.map(name => name.toLocaleLowerCase())).size !== names.length) return invalid(get('wizardPositions'), 'Jede Funktion benötigt einen unterscheidbaren Namen.');
      positionNames = names;
      templates.forEach(template => {
        template.demands = positionNames.map(name => template.demands.find(demand => demand.name === name) || {name, minimum: 1, maximum: 1});
      });
      if (!templates.length) templates.push(newTemplate());
      renderTemplates();
    }
    if (step === 2) {
      for (const template of templates) {
        if (!template.name.trim()) { showError('Bitte jeder Schichtvorlage einen Namen geben.'); return false; }
        if (!template.weekdays.length) { showError(`Für „${template.name}“ mindestens einen Wochentag auswählen.`); return false; }
        if (template.start_time === template.end_time) { showError(`Für „${template.name}“ unterschiedliche Start- und Endzeiten eingeben.`); return false; }
        if (template.demands.some(demand => demand.minimum > demand.maximum)) { showError(`Für „${template.name}“ muss die Höchstbesetzung mindestens der Mindestbesetzung entsprechen.`); return false; }
        if (!template.demands.some(demand => demand.maximum > 0)) { showError(`Für „${template.name}“ wird mindestens eine Funktion mit einer Höchstbesetzung über null benötigt.`); return false; }
      }
    }
    return true;
  }
  function newTemplate() {
    return {name: templates.length ? `Schicht ${templates.length + 1}` : 'Tagschicht', kind: 'day', start_time: '08:00', end_time: '16:00', weekdays: [0, 1, 2, 3, 4], demands: positionNames.map(name => ({name, minimum: 1, maximum: 1}))};
  }
  function renderTemplates() {
    const parent = get('wizardTemplates');
    parent.replaceChildren();
    templates.forEach((template, index) => {
      const box = node('fieldset', undefined, parent);
      box.className = 'wizard-template';
      node('legend', `Schichtvorlage ${index + 1}`, box);
      const grid = node('div', undefined, box);
      grid.className = 'wizard-grid';
      const field = (label, key, type, min, max) => {
        const wrapper = node('label', label, grid);
        wrapper.className = 'wizard-field';
        const input = node('input', undefined, wrapper);
        input.type = type; input.value = template[key]; input.required = true;
        input.dataset.field = key.replace('_time', '');
        if (min !== undefined) input.min = min;
        if (max !== undefined) input.max = max;
        if (type === 'text') input.maxLength = 120;
        input.addEventListener('input', () => { template[key] = input.value; updateSummary(); });
      };
      field('Bezeichnung', 'name', 'text');
      const kindLabel = node('label', 'Dienstart', grid);
      kindLabel.className = 'wizard-field';
      const kind = node('select', undefined, kindLabel);
      kind.dataset.field = 'kind';
      for (const [value, text] of [['day', 'Tag'], ['night', 'Nacht']]) {
        const option = node('option', text, kind); option.value = value;
      }
      kind.value = template.kind;
      kind.addEventListener('change', () => { template.kind = kind.value; });
      field('Beginn', 'start_time', 'time'); field('Ende', 'end_time', 'time');
      const days = node('fieldset', undefined, box);
      days.className = 'wizard-weekdays'; node('legend', 'Wochentage', days);
      weekdays.forEach((name, day) => {
        const label = node('label', undefined, days);
        const check = node('input', undefined, label); check.type = 'checkbox'; check.checked = template.weekdays.includes(day);
        check.setAttribute('aria-label', `${name}, Schichtvorlage ${index + 1}`);
        check.dataset.weekday = day;
        node('span', name, label);
        check.addEventListener('change', () => {
          template.weekdays = check.checked ? [...template.weekdays, day].sort() : template.weekdays.filter(value => value !== day);
          updateSummary();
        });
      });
      const needs = node('div', undefined, box); needs.className = 'wizard-demands';
      template.demands.forEach((demand, position) => {
        const row = node('div', undefined, needs); row.className = 'wizard-demand';
        node('strong', demand.name, row);
        for (const [key, text] of [['minimum', 'Minimum'], ['maximum', 'Maximum']]) {
          const label = node('label', text, row); label.className = 'wizard-field';
          const input = node('input', undefined, label); input.type = 'number'; input.min = 0; input.max = 1000; input.step = 1; input.required = true; input.value = demand[key];
          input.setAttribute('aria-label', `${demand.name} ${text}, Schichtvorlage ${index + 1}`);
          input.dataset.position = position; input.dataset.field = key;
          input.addEventListener('input', () => { demand[key] = input.value === '' ? NaN : Number(input.value); updateSummary(); });
        }
      });
      if (templates.length > 1) {
        const remove = node('button', 'Vorlage entfernen', box); remove.type = 'button'; remove.className = 'secondary';
        remove.setAttribute('aria-label', `Schichtvorlage ${index + 1} entfernen`);
        remove.addEventListener('click', () => { templates.splice(index, 1); renderTemplates(); updateSummary(); });
      }
    });
    get('wizardAddTemplate').disabled = templates.length >= 32;
  }
  function ruleValues() {
    return {min_rest_hours: Number(get('wizardMinRest').value), after_night_rest_hours: Number(get('wizardNightRest').value), max_consecutive_work_days: Number(get('wizardWorkDays').value), max_consecutive_nights: Number(get('wizardNights').value), max_daily_hours: Number(get('wizardDailyHours').value), max_weekly_hours: Number(get('wizardMaxWeeklyHours').value), weekly_rest_hours: Number(get('wizardWeeklyRest').value)};
  }
  function updateSummary() {
    if (step !== 2) return;
    const start = get('wizardStart').value, end = get('wizardEnd').value;
    const dayCount = (utcDate(end) - utcDate(start)) / 86400000 + 1;
    const startDay = (utcDate(start).getUTCDay() + 6) % 7;
    let count = 0, minimum = 0;
    templates.forEach(template => {
      let occurrences = 0;
      for (let day = 0; day < dayCount; day++) if (template.weekdays.includes((startDay + day) % 7)) occurrences++;
      count += occurrences;
      minimum += occurrences * template.demands.reduce((sum, demand) => sum + (Number.isFinite(demand.minimum) ? demand.minimum : 0), 0);
    });
    get('wizardSummary').textContent = `${lines(get('wizardPeople').value).length} Personen · ${positionNames.length} Funktionen · ${count} Schichten · ${minimum} mindestens zu besetzende Plätze`;
    const rules = ruleValues();
    const horizon = Math.max(8, rules.max_consecutive_work_days || 1, rules.max_consecutive_nights || 1, Math.ceil(Math.max(rules.min_rest_hours, rules.after_night_rest_hours) / 24) || 1);
    get('wizardContextLabel').textContent = `Ich bestätige: Außerhalb der angelegten Schichten gibt es keine weiteren Dienste im Randzeitraum ${offsetDate(start, -horizon)} bis ${offsetDate(start, -1)} sowie ${offsetDate(end, 1)} bis ${offsetDate(end, horizon)}. Laufende Schichten über Mitternacht sind berücksichtigt. Andernfalls ergänze ich den Randkontext später.`;
  }
  trigger.addEventListener('click', () => {
    if (busy) return;
    if (fresh) {
      form.reset();
      const today = new Date();
      get('wizardStart').value = dateValue(new Date(today.getFullYear(), today.getMonth(), 1));
      get('wizardEnd').value = dateValue(new Date(today.getFullYear(), today.getMonth() + 1, 0));
      get('wizardTimezone').value = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
      templates = []; positionNames = []; step = 0; fresh = false;
    }
    dialog.showModal(); gotoStep(step);
    if (step === 0) get('wizardName').focus();
  });
  get('wizardCancel').addEventListener('click', () => { if (!busy) dialog.close(); });
  dialog.addEventListener('cancel', event => { if (busy) event.preventDefault(); });
  get('wizardBack').addEventListener('click', () => gotoStep(Math.max(0, step - 1)));
  get('wizardNext').addEventListener('click', () => { if (validateStep()) gotoStep(step + 1); });
  get('wizardAddTemplate').addEventListener('click', () => {
    if (templates.length >= 32) return;
    templates.push(newTemplate()); renderTemplates(); updateSummary();
    get('wizardTemplates').lastElementChild.querySelector('input').focus();
  });
  for (const input of steps[2].querySelectorAll('input[type=number]')) input.addEventListener('input', () => {
    get('wizardRulesConfirmed').checked = false;
    get('wizardContextConfirmed').checked = false;
    updateSummary();
  });
  for (const id of ['wizardStart', 'wizardEnd', 'wizardTimezone', 'wizardPeople', 'wizardPositions']) {
    get(id).addEventListener('input', () => {
      get('wizardContextConfirmed').checked = false;
      if (id === 'wizardPeople' || id === 'wizardPositions') get('wizardApprovalsConfirmed').checked = false;
    });
  }
  form.addEventListener('input', event => event.target.removeAttribute('aria-invalid'));
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy) return;
    if (step < 2) { if (validateStep()) gotoStep(step + 1); return; }
    if (!validateStep()) return;
    const payload = {project_name: get('wizardName').value.trim(), period_start: get('wizardStart').value, period_end: get('wizardEnd').value, timezone: get('wizardTimezone').value.trim(), people: readPeople(), positions: positionNames.map(name => ({name})), shift_templates: templates.map(template => ({name: template.name.trim(), kind: template.kind, start_time: template.start_time, end_time: template.end_time, weekdays: template.weekdays, demands: template.demands.map((demand, position) => ({position, minimum: demand.minimum, maximum: demand.maximum}))})), rules: ruleValues(), rules_confirmed: get('wizardRulesConfirmed').checked, approvals_confirmed: get('wizardApprovalsConfirmed').checked, context_duty_free_confirmed: get('wizardContextConfirmed').checked};
    busy = true;
    const controls = Array.from(form.querySelectorAll('button, input, select, textarea'));
    const disabled = controls.map(control => control.disabled);
    controls.forEach(control => { control.disabled = true; });
    get('wizardCreate').textContent = 'Projekt wird erstellt …';
    form.setAttribute('aria-busy', 'true'); showError('');
    try {
      const response = await fetch('/api/projects/new', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = typeof data.detail === 'string' ? data.detail : Array.isArray(data.detail) ? data.detail.map(item => item.msg).join(' · ') : 'Das Projekt konnte nicht erstellt werden. Bitte Angaben prüfen und erneut versuchen.';
        throw Error(detail);
      }
      if (!window.PlannerApp?.openProject) throw Error('Die Projektansicht ist noch nicht bereit. Bitte erneut versuchen.');
      const opened = await window.PlannerApp.openProject(data.snapshot);
      if (opened) { fresh = true; dialog.close(); }
      else showError('Das Projekt wurde noch nicht geöffnet. Die eingegebenen Angaben bleiben erhalten.');
    } catch (error) {
      showError(error.message || 'Die Verbindung ist fehlgeschlagen. Die eingegebenen Angaben bleiben erhalten.');
    } finally {
      busy = false;
      controls.forEach((control, index) => { control.disabled = disabled[index]; });
      get('wizardCreate').textContent = 'Projekt erstellen';
      form.removeAttribute('aria-busy');
    }
  });
})();
