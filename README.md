# 🚀 Trading 212 v eDavke (Doh-KDVP)

Ta skripta je namenjena vsem, ki uporabljate **Trading 212** in želite hitro ter varno pripraviti XML datoteko za prijavo davka na dobiček (**Doh-KDVP**) na portalu eDavki.

---

## 🛠️ 1. Priprava (samo prvič)

1.  **Namesti Python:** Prenesi ga na [python.org](https://www.python.org/downloads/). 
    *   **Zelo pomembno:** Ob začetku namestitve obvezno obkljukaj polje **"Add Python to PATH"**.
2.  **Namesti Pandas:** To je knjižnica za obdelavo podatkov. Odpri *Ukazni poziv* (v Windowsih vpiši `cmd` v iskalnik ob gumbu Start) in vpiši:
    ```bash
    pip install pandas
    ```

---

## 📂 2. Tvoji podatki

1.  **Izvozi iz Trading 212:** V mapo `input` skopiraj svoje CSV izvoze transakcij.
    *   **💡 Nasvet:** Skopiraj **vse izvoze od samega začetka trgovanja**, ne le za zadnje leto. Skripta potrebuje celotno zgodovino, da pravilno izračuna nabavno vrednost (FIFO) in upošteva pretekle delitve delnic.
2.  **Tečaji:** V mapi `rate` je že vključena datoteka s tečaji za preračun.

---

## ⚙️ 3. Nastavitev leta in podatkov

Z desnim klikom klikni na `main.py` -> **Odpri z (Open with)** -> **Beležnica (Notepad)**.
Na vrhu datoteke pod razdelkom `# --- NASTAVITVE UPORABNIKA ---` spremeni:

*   **`TAX_YEAR`**: Leto, za katero oddajaš (npr. `2025`).
*   **Osebni podatki**: Davčno številko, ime in naslov lahko dopolniš tukaj. 
    *   *Opomba: Tudi če pustiš privzeto, bodo eDavki ob uvozu sami prepoznali tvoj profil in posodobili podatke.*

**Shrani datoteko (`Ctrl + S`)!**

---

## ⚡ 4. Zagon (najhitrejši način)

1.  Odpri mapo, kjer imaš datoteko `main.py`.
2.  **Trik:** Zgoraj v naslovno vrstico okna (kjer piše pot do mape) klikni z miško, pobriši vse, vpiši **`powershell`** in pritisni **Enter**.
3.  V črno okno, ki se odpre, vpiši spodnji ukaz in pritisni Enter:
    ```bash
    python main.py
    ```
4.  Ko skripta zaključi, boš v mapi **`output`** našel pripravljeno XML datoteko.

---

## 📝 5. Oddaja v eDavke

1.  Prijavi se v [eDavke](https://edavki.durs.si/) in odpri obrazec **Doh-KDVP** za ustrezno leto.
2.  Klikni gumb **Uvoz** (zgoraj desno v meniju) in izberi XML datoteko iz mape `output`.
3.  Klikni **Izračun**, preveri podatke in oddaj obrazec.

---

## 💡 Zakaj uporabiti to skripto?

*   **Visoka natančnost:** Uporablja uradne ECB tečaje in visoko število decimalk za minimalna odstopanja.
*   **Stroga deduplikacija:** Če imaš več CSV datotek, ki se časovno prekrivajo, bo skripta samodejno odstranila vse podvojene vnose.
*   **Stock Splits:** Vsebuje logiko za Nvidio in ostale večje splite, kar večina spletnih pretvornikov spregleda, kar povzroči napačen izračun davka.

---

### ☕ Podpora in donacije

Če ti je programček prihranil čas in živce ter je bil izvoz pravilen, sem zelo vesel vsake donacije za kavo ali pivo! Gre za prostovoljni prispevek, ki mi pomaga vzdrževati skripto.

👉 **[Doniraj preko PayPal](https://www.paypal.com/donate/?hosted_button_id=X35CTXP8REUVQ)**

---

**Opozorilo:** Skripta je pripomoček in ne nadomešča uradnih nasvetov. Pred oddajo na portal eDavki obvezno preglejte izračune. Avtor ne prevzema odgovornosti za morebitne napake v davčni napovedi.
