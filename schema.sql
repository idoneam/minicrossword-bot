CREATE TABLE IF NOT EXISTS `Scores` (
    `ID` INTEGER,
    `Name` TEXT NOT NULL,
    `Date` TEXT,
    `Score` INTEGER NOT NULL,
    PRIMARY KEY (ID, Date)
);

CREATE TABLE IF NOT EXISTS `Ranking` (
    `ID` INTEGER PRIMARY KEY,
    `Name` TEXT NOT NULL,
    `RegAvg` INTEGER,
    `SatAvg` INTEGER
);
