-- Sample: employee bonus stored procedure (used by tests)

IF EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[usp_ProcessEmployeeBonus]') AND type in (N'P', N'PC'))
    DROP PROCEDURE [dbo].[usp_ProcessEmployeeBonus];
GO

/*
================================================================================
 Object:     dbo.usp_ProcessEmployeeBonus
 Purpose:    Apply a bonus to an employee and record the change in AuditLog
--------------------------------------------------------------------------------
 Mod Date     Modified By     Description
 -----------  --------------  -------------------------------------------------
 2024-03-12   J.Smith         Initial release — bonus UPDATE + audit INSERT
 2025-01-08   A.Patel         Wrapped DML in TRY/CATCH; added @IsSuccess output
================================================================================
*/

CREATE PROCEDURE dbo.usp_ProcessEmployeeBonus
    @EmployeeID INT,
    @BonusAmount DECIMAL(18, 2)
AS
BEGIN
    SET NOCOUNT ON

    DECLARE @IsSuccess BIT = 0
    DECLARE @ErrMsg NVARCHAR(4000)

    -- Process bonus inside TRY/CATCH
    BEGIN TRY
        UPDATE dbo.Employees
        SET Bonus = Bonus + @BonusAmount,
            LastModified = GETDATE()
        WHERE EmployeeID = @EmployeeID

        INSERT INTO dbo.AuditLog (EmployeeID, LogMessage, CreatedDate)
        VALUES (@EmployeeID, CONCAT('Bonus processed: $', @BonusAmount), GETDATE())

        SET @IsSuccess = 1
    END TRY
    BEGIN CATCH
        SET @IsSuccess = 0
        SET @ErrMsg = ERROR_MESSAGE()
    END CATCH
END

GO