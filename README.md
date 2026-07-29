# 🚀 Trading 212 ➡️ eDavke (Doh-KDVP)

Živijo! Če trguješ na Trading 212 in si kdaj poskusil ročno vnašati vse tiste nakupe in prodaje v eDavke, veš, da je to prava muka. Ta skripta je tukaj, da ti olajša življenje – prebere tvoje CSV izvoze in ti pripravi XML datoteko, ki jo samo uvoziš na portal, in stvar je rešena.

---

## 🛠️ 1. Kaj rabiš na začetku?

1.  **Inštaliraj Python:** Prenesi ga na [python.org](https://www.python.org/downloads/).
    -   **Nujno:** Ko zaženeš inštalacijo, obvezno obkljukaj polje **"Add Python to PATH"**, sicer računalnik ne bo vedel, kaj bi rad od njega.
2.  **Namesti knjižnice:** Odpri _Ukazni poziv_ (v iskanje napiši `cmd`) in skopiraj spodnji ukaz:
    ```bash
    pip install -r requirements.txt
    ```

---

## 📂 2. Pripravi svoje podatke

1.  Na Trading 212 izvozi svoje transakcije v **CSV** formatu.
2.  Vse te datoteke preprosto vrzi v mapo `input`.
    -   **💡 Nasvet:** Najbolje je, da skopiraš **vse izvoze od samega začetka**, ko si začel trgovati. Skripta namreč rabi celotno zgodovino, da pravilno poračuna nabavno ceno po metodi **FIFO** (najprej prodaj tisto, kar si najprej kupil).

---

## ⚙️ 3. Tvoji podatki (`settings.py`)

Preimenuj datoteko `settings.py.template` v `settings.py` (z desnim klikom -> Odpri z Beležnico/Notepad) in uredi:

-   `TAX_YEAR`: Vpiši leto, za katero oddajaš (npr. 2025).
-   `TAX_NUMBER`, `NAME`, `ADDRESS`...: Vpiši svoje podatke, da bodo eDavki vedeli, čigava je napoved.
-   `TAX_RATE`: To pustiš na 0.25 (25 %), razen če imaš kakšen poseben razlog za spremembo.

---

## ⚡ 4. Akcija!

1.  Pojdi v mapo, kjer imaš skripto. Zgoraj v naslovno vrstico raziskovalca (tam, kjer piše pot do mape) napiši **`cmd`** in pritisni Enter.
2.  V črno okno, ki se odpre, napiši:
    ```bash
    python main.py
    ```
3.  **V tem oknu boš takoj videl:**
    -   **Realni dobiček:** Koliko si dejansko zaslužil na borzi.
    -   **FURS dobiček:** Tista številka, od katere se računa davek (že vštet 1 % stroškov).
    -   **Stanje portfelja:** Pregled, kaj vse še držiš na računu.

XML datoteka te bo čakala v mapi **`output`**. To datoteko nato preprosto uvoziš v eDavke pod obrazec Doh-KDVP.

---

## 💡 Zakaj bi sploh uporabljal to skripto?

-   **Samodejni ECB tečaji:** Skripta sama pobere uradne tečaje z interneta na dan posla. Nič več ročnega preračunavanja iz dolarjev v evre.
-   **FIFO metoda:** Vse se pravilno popari po vrstnem redu, kot zahteva zakon.
-   **Manjši davek:** Program avtomatsko prišteje 1 % h kupni ceni in odšteje 1 % od prodajne, kar ti malo zniža davčno osnovo (priznani stroški).
-   **Stock Splits:** Če si imel Nvidio ali podobne delnice, veš, da so bili spliti. Skripta to zrihta, da ne boš v minusu s količino.

---

### ☕ Podpora in donacije

Če ti je skripta prihranila čas in denar, bom vesel donacije za kavo ali pivo!

👉 **[Doniraj preko PayPal](https://www.paypal.com/donate/?hosted_button_id=X35CTXP8REUVQ)**

---

**Pazi:** Program je informativni pripomoček. Preden oddaš na eDavke, vseeno malo preveri številke, če se ti zdi vse smiselno. Za svojo davčno napoved odgovarjaš sam.

---

### 🤝 Zasluge / Attribution
Ta projekt je bil povzet in izboljšan na podlagi odprtokodne rešitve: [Neophytez/t212-edavki](https://github.com/Neophytez/t212-edavki). Hvala originalnemu avtorju za postavljene temelje!
