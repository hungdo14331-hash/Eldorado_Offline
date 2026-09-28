/*
========================================================
BUSIDOL WIKI
Main UI Controller
========================================================
*/


/*
========================================================
DOM - GLOBAL VIEWS
========================================================
*/

const navButtons =
    document.querySelectorAll(
        ".nav-button"
    );

const wikiViews = {

    characters:
        document.getElementById(
            "charactersView"
        ),

    missile:
        document.getElementById(
            "missileView"
        ),

    tower:
        document.getElementById(
            "towerView"
        )
};


/*
========================================================
DOM - CHARACTER
========================================================
*/

const characterGrid =
    document.getElementById(
        "characterGrid"
    );

const searchInput =
    document.getElementById(
        "searchInput"
    );

const starFilter =
    document.getElementById(
        "starFilter"
    );

const characterCount =
    document.getElementById(
        "characterCount"
    );

const sidebarCharacterCount =
    document.getElementById(
        "sidebarCharacterCount"
    );


/*
========================================================
DOM - MODAL
========================================================
*/

const modal =
    document.getElementById(
        "characterModal"
    );

const closeModalButton =
    document.getElementById(
        "closeModal"
    );

const detailImage =
    document.getElementById(
        "detailImage"
    );

const detailName =
    document.getElementById(
        "detailName"
    );

const detailStars =
    document.getElementById(
        "detailStars"
    );

const detailId =
    document.getElementById(
        "detailId"
    );

const detailMaxLevel =
    document.getElementById(
        "detailMaxLevel"
    );

const detailHpStart =
    document.getElementById(
        "detailHpStart"
    );

const detailHpEnd =
    document.getElementById(
        "detailHpEnd"
    );

const detailApStart =
    document.getElementById(
        "detailApStart"
    );

const detailApEnd =
    document.getElementById(
        "detailApEnd"
    );

const levelTableBody =
    document.getElementById(
        "levelTableBody"
    );

const modalBackdrop =
    modal
        ? modal.querySelector(
            ".modal-backdrop"
        )
        : null;


/*
========================================================
DOM - MISSILE
========================================================
*/

const missileTableBody =
    document.getElementById(
        "missileTableBody"
    );

const missileLevelSearch =
    document.getElementById(
        "missileLevelSearch"
    );

const missileLv1Power =
    document.getElementById(
        "missileLv1Power"
    );

const missileMaxPower =
    document.getElementById(
        "missileMaxPower"
    );


/*
========================================================
DOM - TOWER
========================================================
*/

const towerTableBody =
    document.getElementById(
        "towerTableBody"
    );

const towerLevelSearch =
    document.getElementById(
        "towerLevelSearch"
    );

const towerLv1Hp =
    document.getElementById(
        "towerLv1Hp"
    );

const towerMaxHp =
    document.getElementById(
        "towerMaxHp"
    );


/*
========================================================
STATE
========================================================
*/

let selectedStar =
    "all";


/*
========================================================
UTILITIES
========================================================
*/

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
        .replaceAll(
            "&",
            "&amp;"
        )
        .replaceAll(
            "<",
            "&lt;"
        )
        .replaceAll(
            ">",
            "&gt;"
        )
        .replaceAll(
            '"',
            "&quot;"
        )
        .replaceAll(
            "'",
            "&#039;"
        );
}


/*
========================================================
VIEW SWITCHING
========================================================
*/

function showView(viewName) {

    Object.entries(
        wikiViews
    )
    .forEach(
        ([name, element]) => {

            if (!element) {
                return;
            }

            element.classList.toggle(
                "active",
                name === viewName
            );
        }
    );


    navButtons.forEach(
        button => {

            button.classList.toggle(
                "active",
                button.dataset.view ===
                    viewName
            );
        }
    );


    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });
}


/*
========================================================
CHARACTER CARD
========================================================
*/

function createCharacterCard(
    character
) {

    const card =
        document.createElement(
            "article"
        );


    card.className =
        "character-card";


    card.dataset.characterId =
        String(character.id);


    const imageUrl =
        getCharacterPortrait(
            character
        );


    card.innerHTML = `

        <div class="character-image">

            <span class="character-id">
                ID ${character.id}
            </span>

            <img
                src="${imageUrl}"
                alt="${escapeHtml(
                    character.name
                )}"
                loading="lazy"
            >

            <div class="image-fallback">

                <strong>
                    ID ${character.id}
                </strong>

                <span>
                    ${escapeHtml(
                        character.name
                    )}
                </span>

                <small>
                    Portrait unavailable
                </small>

            </div>

        </div>


        <div class="character-body">

            <div class="character-stars">
                ${makeStars(
                    character.star
                )}
            </div>


            <div class="character-name">
                ${escapeHtml(
                    character.name
                )}
            </div>


            <div class="character-stats">

                <div class="mini-stat">

                    <span>
                        HP
                    </span>

                    <strong>
                        ${formatNumber(
                            character.hpStart
                        )}
                        →
                        ${formatNumber(
                            character.hpEnd
                        )}
                    </strong>

                </div>


                <div class="mini-stat">

                    <span>
                        AP
                    </span>

                    <strong>
                        ${formatNumber(
                            character.apStart
                        )}
                        →
                        ${formatNumber(
                            character.apEnd
                        )}
                    </strong>

                </div>


                <div class="mini-stat">

                    <span>
                        Level
                    </span>

                    <strong>
                        1 →
                        ${character.maxLevel}
                    </strong>

                </div>


                <div class="mini-stat">

                    <span>
                        Asset
                    </span>

                    <strong>
                        ${escapeHtml(
                            character.sourceAsset
                        )}
                    </strong>

                </div>

            </div>

        </div>
    `;


    const image =
        card.querySelector(
            "img"
        );


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


/*
========================================================
RENDER CHARACTERS
========================================================
*/

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
                    selectedStar ===
                        "all"
                    ||
                    character.star ===
                        Number(
                            selectedStar
                        );


                const searchText =
                    [
                        character.name,
                        character.id,
                        character.star,
                        character.sourceAsset,
                        `ga_ally_${character.id}.jpg`
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
            String(
                filtered.length
            );
    }


    if (sidebarCharacterCount) {

        sidebarCharacterCount.textContent =
            String(
                CHARACTERS.length
            );
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


/*
========================================================
CHARACTER DETAIL
========================================================
*/

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
            String(
                character.id
            );
    }


    if (detailMaxLevel) {

        detailMaxLevel.textContent =
            String(
                character.maxLevel
            );
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


    /*
    IMAGE
    */

    if (detailImage) {

        detailImage.onerror =
            null;


        detailImage.style.display =
            "";


        detailImage.src =
            getCharacterPortrait(
                character
            );


        detailImage.alt =
            character.name;


        detailImage.onerror =
            () => {

                detailImage.style.display =
                    "none";
            };
    }


    /*
    LEVEL TABLE
    */

    if (levelTableBody) {

        levelTableBody.innerHTML =
            "";


        getCharacterLevelStats(
            character
        )
        .forEach(
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
                        ${formatNumber(
                            stat.ap
                        )}
                    </td>

                    <td>
                        ${formatNumber(
                            stat.hp
                        )}
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


/*
========================================================
CLOSE MODAL
========================================================
*/

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


/*
========================================================
MISSILE TABLE
========================================================
*/

function renderMissileTable() {

    if (!missileTableBody) {
        return;
    }


    let levels =
        MISSILE_LEVELS;


    const requestedLevel =
        Number(
            missileLevelSearch
                ?.value
        );


    if (
        requestedLevel >= 1
        &&
        requestedLevel <=
            MISSILE_MAX_LEVEL
    ) {

        levels =
            MISSILE_LEVELS.filter(
                item =>
                    item.level ===
                    requestedLevel
            );
    }


    missileTableBody.innerHTML =
        "";


    levels.forEach(
        item => {

            const row =
                document.createElement(
                    "tr"
                );


            row.innerHTML = `

                <td>
                    ${item.level}
                </td>

                <td>
                    ${formatNumber(
                        item.power
                    )}
                </td>

                <td>
                    ${item.normalVisualTier}
                </td>
            `;


            missileTableBody.appendChild(
                row
            );
        }
    );
}


/*
========================================================
TOWER TABLE
========================================================
*/

function renderTowerTable() {

    if (!towerTableBody) {
        return;
    }


    let levels =
        TOWER_LEVELS;


    const requestedLevel =
        Number(
            towerLevelSearch
                ?.value
        );


    if (
        requestedLevel >= 1
        &&
        requestedLevel <=
            TOWER_MAX_LEVEL
    ) {

        levels =
            TOWER_LEVELS.filter(
                item =>
                    item.level ===
                    requestedLevel
            );
    }


    towerTableBody.innerHTML =
        "";


    levels.forEach(
        item => {

            const row =
                document.createElement(
                    "tr"
                );


            row.innerHTML = `

                <td>
                    ${item.level}
                </td>

                <td>
                    ${formatNumber(
                        item.hp
                    )}
                </td>

                <td>
                    ${item.normalVisualTier}
                </td>
            `;


            towerTableBody.appendChild(
                row
            );
        }
    );
}


/*
========================================================
SUMMARY VALUES
========================================================
*/

function updateSystemSummary() {

    if (missileLv1Power) {

        missileLv1Power.textContent =
            formatNumber(
                getMissileBasePower(
                    1
                )
            );
    }


    if (missileMaxPower) {

        missileMaxPower.textContent =
            formatNumber(
                getMissileBasePower(
                    MISSILE_MAX_LEVEL
                )
            );
    }


    if (towerLv1Hp) {

        towerLv1Hp.textContent =
            formatNumber(
                getTowerBaseHp(
                    1
                )
            );
    }


    if (towerMaxHp) {

        towerMaxHp.textContent =
            formatNumber(
                getTowerBaseHp(
                    TOWER_MAX_LEVEL
                )
            );
    }
}


/*
========================================================
EVENTS
========================================================
*/

navButtons.forEach(
    button => {

        button.addEventListener(
            "click",
            () => {

                showView(
                    button.dataset.view
                );
            }
        );
    }
);


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


if (missileLevelSearch) {

    missileLevelSearch.addEventListener(
        "input",
        renderMissileTable
    );
}


if (towerLevelSearch) {

    towerLevelSearch.addEventListener(
        "input",
        renderTowerTable
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
            event.key ===
            "Escape"
        ) {

            closeModal();
        }
    }
);


/*
========================================================
INITIALIZE
========================================================
*/

renderCharacters();

renderMissileTable();

renderTowerTable();

updateSystemSummary();

showView(
    "characters"
);