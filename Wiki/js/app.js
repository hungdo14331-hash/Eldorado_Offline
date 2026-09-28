/*
========================================================
BUSIDOL WIKI
Character UI Controller
========================================================

Lưu ý:
data/characters.js phải được load trước js/app.js.
========================================================
*/

const characterGrid =
    document.getElementById("characterGrid");

const searchInput =
    document.getElementById("searchInput");

const starFilter =
    document.getElementById("starFilter");

const characterCount =
    document.getElementById("characterCount");

const modal =
    document.getElementById("characterModal");

const closeModalButton =
    document.getElementById("closeModal");

const detailImage =
    document.getElementById("detailImage");

const detailName =
    document.getElementById("detailName");

const detailStars =
    document.getElementById("detailStars");

const detailId =
    document.getElementById("detailId");

const detailMaxLevel =
    document.getElementById("detailMaxLevel");

const detailHpStart =
    document.getElementById("detailHpStart");

const detailHpEnd =
    document.getElementById("detailHpEnd");

const detailApStart =
    document.getElementById("detailApStart");

const detailApEnd =
    document.getElementById("detailApEnd");

const levelTableBody =
    document.getElementById("levelTableBody");

const modalBackdrop =
    modal
        ? modal.querySelector(".modal-backdrop")
        : null;

let selectedStar = "all";


function formatNumber(number) {
    return Number(number)
        .toLocaleString("en-US");
}


function makeStars(star) {
    return "★".repeat(
        Math.max(
            0,
            Number(star) || 0
        )
    );
}


function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


function getCharacterAsset(character) {
    return getCharacterPortrait(
        character
    );
}


function createCharacterCard(character) {
    const card =
        document.createElement("article");

    card.className =
        "character-card";

    card.dataset.characterId =
        String(character.id);

    const imageUrl =
        getCharacterAsset(character);

    const imageMarkup =
        imageUrl
        ?
        `
            <img
                src="${imageUrl}"
                alt="${escapeHtml(character.name)}"
                loading="lazy"
            >
        `
        :
        "";

    card.innerHTML = `

        <div class="character-image">

            <span class="character-id">
                ID ${character.id}
            </span>

            ${imageMarkup}

            <div class="image-fallback">

                <strong>
                    ID ${character.id}
                </strong>

                <span>
                    ${escapeHtml(character.name)}
                </span>

                <small>
                    Chưa có portrait
                </small>

            </div>

        </div>


        <div class="character-body">

            <div class="character-stars">
                ${makeStars(character.star)}
            </div>

            <div class="character-name">
                ${escapeHtml(character.name)}
            </div>

            <div class="character-stats">

                <div class="mini-stat">

                    <span>
                        HP
                    </span>

                    <strong class="hp-text">
                        ${formatNumber(character.hpStart)}
                        →
                        ${formatNumber(character.hpEnd)}
                    </strong>

                </div>


                <div class="mini-stat">

                    <span>
                        AP
                    </span>

                    <strong class="ap-text">
                        ${formatNumber(character.apStart)}
                        →
                        ${formatNumber(character.apEnd)}
                    </strong>

                </div>


                <div class="mini-stat">

                    <span>
                        Level
                    </span>

                    <strong>
                        1 → ${character.maxLevel}
                    </strong>

                </div>


                <div class="mini-stat">

                    <span>
                        ID
                    </span>

                    <strong>
                        ${character.id}
                    </strong>

                </div>

            </div>

        </div>
    `;

    const image =
        card.querySelector("img");

    const fallback =
        card.querySelector(
            ".image-fallback"
        );

    if (image) {
        image.addEventListener(
            "load",
            () => {
                if (fallback) {
                    fallback.style.display =
                        "none";
                }
            }
        );

        image.addEventListener(
            "error",
            () => {
                image.style.display =
                    "none";

                if (fallback) {
                    fallback.style.display =
                        "flex";
                }
            }
        );
    }
    else if (fallback) {
        fallback.style.display =
            "flex";
    }

    card.addEventListener(
        "click",
        () => {
            openCharacterDetail(
                character
            );
        }
    );

    return card;
}


function renderCharacters() {
    if (
        !characterGrid
        ||
        !searchInput
    ) {
        return;
    }

    const search =
        searchInput.value
            .trim()
            .toLowerCase();

    const filtered =
        CHARACTERS.filter(
            character => {

                const matchStar =
                    selectedStar === "all"
                    ||
                    character.star ===
                    Number(selectedStar);

                const portraitName =
                    `ga_ally_${character.id}.jpg`;

                const searchText =
                    [
                        character.name,
                        character.id,
                        character.star,
                        character.sourceAsset,
                        portraitName
                    ]
                    .join(" ")
                    .toLowerCase();

                const matchSearch =
                    searchText.includes(
                        search
                    );

                return (
                    matchStar
                    &&
                    matchSearch
                );
            }
        );

    characterGrid.innerHTML =
        "";

    if (characterCount) {
        characterCount.textContent =
            String(filtered.length);
    }

    if (
        filtered.length === 0
    ) {
        characterGrid.innerHTML = `

            <div class="empty-result">
                Không tìm thấy nhân vật.
            </div>
        `;

        return;
    }

    filtered.forEach(
        character => {
            characterGrid.appendChild(
                createCharacterCard(
                    character
                )
            );
        }
    );
}


function openCharacterDetail(
    character
) {
    if (!modal) {
        return;
    }

    if (detailName) {
        detailName.textContent =
            character.name;
    }

    if (detailStars) {
        detailStars.textContent =
            makeStars(
                character.star
            );
    }

    if (detailId) {
        detailId.textContent =
            String(character.id);
    }

    if (detailMaxLevel) {
        detailMaxLevel.textContent =
            String(character.maxLevel);
    }

    if (detailHpStart) {
        detailHpStart.textContent =
            formatNumber(
                character.hpStart
            );
    }

    if (detailHpEnd) {
        detailHpEnd.textContent =
            formatNumber(
                character.hpEnd
            );
    }

    if (detailApStart) {
        detailApStart.textContent =
            formatNumber(
                character.apStart
            );
    }

    if (detailApEnd) {
        detailApEnd.textContent =
            formatNumber(
                character.apEnd
            );
    }

    if (detailImage) {
        const imageUrl =
            getCharacterAsset(
                character
            );

        detailImage.onerror =
            null;

        if (imageUrl) {
            detailImage.style.display =
                "";

            detailImage.src =
                imageUrl;

            detailImage.alt =
                character.name;

            detailImage.onerror =
                () => {
                    detailImage.style.display =
                        "none";
                };
        }
        else {
            detailImage.removeAttribute(
                "src"
            );

            detailImage.style.display =
                "none";
        }
    }

    if (levelTableBody) {
        levelTableBody.innerHTML =
            "";

        const stats =
            getCharacterLevelStats(
                character
            );

        stats.forEach(
            stat => {

                const row =
                    document.createElement(
                        "tr"
                    );

                row.innerHTML = `

                    <td>
                        ${stat.level}
                    </td>

                    <td>
                        ${formatNumber(stat.ap)}
                    </td>

                    <td>
                        ${formatNumber(stat.hp)}
                    </td>
                `;

                levelTableBody.appendChild(
                    row
                );
            }
        );
    }

    modal.classList.add(
        "open"
    );

    document.body.style.overflow =
        "hidden";
}


function closeModal() {
    if (!modal) {
        return;
    }

    modal.classList.remove(
        "open"
    );

    document.body.style.overflow =
        "";
}


if (searchInput) {
    searchInput.addEventListener(
        "input",
        renderCharacters
    );
}


if (starFilter) {
    starFilter.addEventListener(
        "click",
        event => {

            const button =
                event.target.closest(
                    ".star-button"
                );

            if (!button) {
                return;
            }

            document
                .querySelectorAll(
                    ".star-button"
                )
                .forEach(
                    item => {
                        item.classList.remove(
                            "active"
                        );
                    }
                );

            button.classList.add(
                "active"
            );

            selectedStar =
                button.dataset.star
                ||
                "all";

            renderCharacters();
        }
    );
}


if (closeModalButton) {
    closeModalButton.addEventListener(
        "click",
        closeModal
    );
}


if (modalBackdrop) {
    modalBackdrop.addEventListener(
        "click",
        closeModal
    );
}


document.addEventListener(
    "keydown",
    event => {
        if (
            event.key === "Escape"
        ) {
            closeModal();
        }
    }
);


renderCharacters();
