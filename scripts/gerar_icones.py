"""Gera os ícones do app (PNG) com a identidade do site: fundo musgo e dois elos entrelaçados.

Uso (na raiz do projeto):  python scripts/gerar_icones.py
Só precisa rodar de novo se mudar o desenho ou as cores.
"""
from pathlib import Path

from PIL import Image, ImageDraw

MUSGO = (45, 92, 68)
SINAL = (240, 180, 0)
PAPEL = (255, 255, 255)
SAIDA = Path(__file__).resolve().parent.parent / 'static' / 'icons'
ESCALA = 4  # desenha em tamanho maior e reduz, para as bordas ficarem lisas


def elos(tamanho, ocupacao):
    """Desenha em `tamanho` px; `ocupacao` é a fração do ícone usada pelo desenho (margem de segurança)."""
    t = tamanho * ESCALA
    img = Image.new('RGB', (t, t), MUSGO)
    d = ImageDraw.Draw(img)

    largura = t * ocupacao            # largura total dos dois elos juntos
    altura = largura * 0.52           # cada elo é um "comprimido" arredondado
    espessura = altura * 0.24
    deslocamento = largura * 0.30     # quanto um elo avança sobre o outro
    cx, cy = t / 2, t / 2
    comprimento = largura - deslocamento

    def elo(x0, cor):
        caixa = [x0, cy - altura / 2, x0 + comprimento, cy + altura / 2]
        d.rounded_rectangle(caixa, radius=altura / 2, outline=cor, width=int(espessura))

    esq = cx - largura / 2
    elo(esq, PAPEL)
    elo(esq + deslocamento, SINAL)

    # Entrelaçado: o elo amarelo já está por cima do branco. Na metade de baixo da região onde
    # os dois se cruzam, repinta o branco por cima, para um passar "por dentro" do outro.
    so_branco = Image.new('RGB', (t, t), MUSGO)
    ImageDraw.Draw(so_branco).rounded_rectangle(
        [esq, cy - altura / 2, esq + comprimento, cy + altura / 2],
        radius=altura / 2, outline=PAPEL, width=int(espessura),
    )
    regiao = Image.new('L', (t, t), 0)
    ImageDraw.Draw(regiao).rectangle(
        [esq + deslocamento, cy, esq + comprimento, cy + altura], fill=255
    )
    cobre_so_o_branco = Image.eval(
        Image.composite(Image.new('L', (t, t), 255), Image.new('L', (t, t), 0),
                        so_branco.convert('L').point(lambda v: 255 if v > 200 else 0)),
        lambda v: v,
    )
    mascara = Image.composite(regiao, Image.new('L', (t, t), 0), cobre_so_o_branco)
    img.paste(so_branco, (0, 0), mascara)

    return img.resize((tamanho, tamanho), Image.LANCZOS)


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    # "any": desenho grande. "maskable": desenho dentro da zona segura (80% central), pois o sistema recorta as bordas.
    for nome, tamanho, ocupacao in [
        ('icone-192.png', 192, 0.74),
        ('icone-512.png', 512, 0.74),
        ('icone-maskable-512.png', 512, 0.52),
        ('apple-touch-icon.png', 180, 0.70),
    ]:
        elos(tamanho, ocupacao).save(SAIDA / nome, optimize=True)
        print('gerado', nome)


if __name__ == '__main__':
    main()
