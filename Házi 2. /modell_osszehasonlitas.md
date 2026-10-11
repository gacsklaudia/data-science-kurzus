# Titanic Modellösszehasonlítás – Hiperparaméter Optimálása

## Feladat összefoglalása
A feladatom az volt, hogy két modellt válasszak ki a hat közül (Random Forest és Gradient Boosting), mindkettőnél teszteljem legalább 3-3 különböző hiperparaméter-beállítást, és nyomon kövessem külön a tanuló és teszt pontosságot, hogy azonosítsam az overfitting jeleit.

## Modellválasztás
- **Random Forest**: `n_estimators`, `max_depth`
- **Gradient Boosting**: `learning_rate`, `n_estimators`, `max_depth`

## Konfigurációk és Eredmények

| Modell | Hiperparaméterek | Train Acc | Test Acc | Gap | Megj |
|--------|------------------|-----------|----------|-----|------|
| RF_default | random_state=42 | 0.985 | 0.799 | 0.186 | Alapértelmezett |
| RF_depth8_200 | n_est=200, max_depth=8 | 0.913 | 0.820 | 0.093 | Jó egyensúly |
| RF_depth12_500 | n_est=500, max_depth=12 | 0.980 | 0.793 | 0.187 | Overfitting |
| GB_lr0.05_100 | lr=0.05, n_est=100 | 0.893 | 0.809 | 0.084 | Nagyon jó |
| GB_lr0.05_200 | lr=0.05, n_est=200, d=3 | 0.910 | 0.825 | 0.085 | **Legjobb** |
| GB_lr0.1_500 | lr=0.1, n_est=500, d=5 | 0.965 | 0.799 | 0.166 | Erős overfitting |

## Elemzés

### Legjobb Beállítás
**Gradient Boosting: `learning_rate=0.05, n_estimators=200, max_depth=3`**

Ez a konfiguráció a legjobb, mert jól egyensúlyozza a bias és variance közötti kompromisszumot. A teszt pontosság (0.825) magas, és a train-test szakadék (0.085) viszonylag kicsi. A lassabb tanulási ráta (0.05) és a korlátozottabb mélység (3) azt jelenti, hogy a modell fokozatosan tanul, ami stabilabb generalizációhoz vezet.

### Overfitting Megfigyelések

1. **RF_default és RF_depth12_500**: Az alapértelmezett Random Forest és a túl sok fa/mély fa beállítás mutatja a legerőteljesebb overfitting jeleit. A train pontosság >0.98, de a teszt pontosság csak 0.79 körül van – ez ~0.19-es szakadék nagyon nagy.

2. **GB_lr0.1_500**: A túl agresszív tanulási ráta (0.1) és a sok iteráció (500) kombinációja szintén erős overfittinghez vezet (~0.166-os gap). Az érzékeny beállítások miatt a modell túlságosan rá tanul a tanító adatokra.

3. **RF_depth8_200 és GB_lr0.05_100/200**: Ezek a moderált beállítások sokkal kevesebb overfittinget mutatnak (<0.1-es gap). Az eredmény azt sugallja, hogy az egyensúlyozottabb komplexitás jobb általánosításhoz vezet.

## Konklúzió
A Gradient Boosting `learning_rate=0.05, n_estimators=200, max_depth=3` beállítása az ideális választás a Titanic adatsoron, mivel stabil, jó teszt pontosságot és minimális train-test különbséget biztosít. A Random Forest jobban overfitel az alapértelmezett hiperparaméterekkel, de a kalibrálás (max_depth korlátozás) segíthet. Az overfitting legegyértelműbb jelei az összes modellnél akkor jelennek meg, amikor túl sok paramétert engedünk (mély fák, sok fa, vagy agresszív tanulási ráta).
